import json
import boto3
import pandas as pd
import io
import os
import urllib3
from datetime import datetime

s3_client = boto3.client("s3")
http = urllib3.PoolManager()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET")  # e.g. "your-dq-results-bucket"


def run_quality_checks(df: pd.DataFrame, filename: str) -> dict:
    """Run data quality checks and return a structured report."""
    issues = []
    stats = {}

    total_rows = len(df)
    total_cols = len(df.columns)
    stats["total_rows"] = total_rows
    stats["total_columns"] = total_cols

    # 1. Null checks
    null_counts = df.isnull().sum()
    null_pct = (null_counts / total_rows * 100).round(2)
    null_issues = null_counts[null_counts > 0]
    if not null_issues.empty:
        for col, count in null_issues.items():
            issues.append({
                "type": "NULL_VALUES",
                "column": col,
                "detail": f"{count} nulls ({null_pct[col]}% of rows)"
            })

    # 2. Duplicate check
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        issues.append({
            "type": "DUPLICATE_ROWS",
            "column": "ALL",
            "detail": f"{dup_count} duplicate rows found ({round(dup_count/total_rows*100, 2)}%)"
        })

    # 3. Numeric outliers (Z-score > 3)
    numeric_cols = df.select_dtypes(include=["number"]).columns
    for col in numeric_cols:
        mean = df[col].mean()
        std = df[col].std()
        if std > 0:
            outliers = df[(df[col] - mean).abs() > 3 * std]
            if len(outliers) > 0:
                issues.append({
                    "type": "OUTLIERS",
                    "column": col,
                    "detail": f"{len(outliers)} outlier rows (Z-score > 3), range: [{df[col].min()}, {df[col].max()}]"
                })

    # 4. Schema summary
    stats["column_types"] = df.dtypes.astype(str).to_dict()
    stats["null_percentage_per_column"] = null_pct.to_dict()

    passed = len(issues) == 0
    return {
        "filename": filename,
        "passed": passed,
        "total_issues": len(issues),
        "issues": issues,
        "stats": stats
    }


def explain_with_claude(report: dict) -> str:
    """Call Claude API to generate a plain-English explanation of data quality issues."""
    if report["passed"]:
        return "✅ All data quality checks passed. No issues found."

    issues_text = "\n".join([
        f"- [{i['type']}] Column '{i['column']}': {i['detail']}"
        for i in report["issues"]
    ])

    prompt = f"""You are a data quality analyst. A data pipeline has detected the following issues 
in the file '{report['filename']}' ({report['stats']['total_rows']} rows, {report['stats']['total_columns']} columns):

{issues_text}

Please provide:
1. A plain-English summary of what went wrong (2-3 sentences, non-technical)
2. The likely root cause for each issue
3. Recommended fix for each issue

Be concise and actionable. Format your response clearly with numbered sections."""

    payload = {
        "model": "claude-sonnet-4-5",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}]
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }

    response = http.request(
        "POST",
        "https://api.anthropic.com/v1/messages",
        body=json.dumps(payload).encode("utf-8"),
        headers=headers
    )

    result = json.loads(response.data.decode("utf-8"))
    print(f"Claude API response: {result}")  # debug line
    if "content" not in result:
        return f"AI explanation unavailable: {result.get('error', result)}"
    return result["content"][0]["text"]


def lambda_handler(event, context):
    """
    Triggered by S3 PUT event.
    Reads CSV, runs quality checks, calls Claude API for explanation,
    saves results back to S3.
    """
    # Parse S3 event
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]
    filename = key.split("/")[-1]

    print(f"Processing file: s3://{bucket}/{key}")

    # Read CSV from S3
    response = s3_client.get_object(Bucket=bucket, Key=key)
    df = pd.read_csv(io.BytesIO(response["Body"].read()))

    # Run quality checks
    report = run_quality_checks(df, filename)
    print(f"Quality check complete. Passed: {report['passed']}, Issues: {report['total_issues']}")

    # Get AI explanation
    explanation = explain_with_claude(report)
    report["ai_explanation"] = explanation
    report["processed_at"] = datetime.utcnow().isoformat()

    # Save result to S3
    result_key = f"quality-results/{filename.replace('.csv', '')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    s3_client.put_object(
        Bucket=RESULTS_BUCKET,
        Key=result_key,
        Body=json.dumps(report, indent=2),
        ContentType="application/json"
    )

    print(f"Results saved to s3://{RESULTS_BUCKET}/{result_key}")

    return {
        "statusCode": 200,
        "body": json.dumps({
            "file": filename,
            "passed": report["passed"],
            "issues_found": report["total_issues"],
            "result_saved_to": result_key
        })
    }
