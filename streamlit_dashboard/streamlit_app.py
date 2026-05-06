import streamlit as st
import boto3
import json
import pandas as pd
from datetime import datetime
import os

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Data Quality Monitor",
    page_icon="🔍",
    layout="wide"
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0f1117; }
    .metric-card {
        background: #1e2130;
        border-radius: 10px;
        padding: 20px;
        border-left: 4px solid #4CAF50;
        margin-bottom: 10px;
    }
    .fail-card {
        background: #1e2130;
        border-radius: 10px;
        padding: 20px;
        border-left: 4px solid #f44336;
        margin-bottom: 10px;
    }
    .ai-box {
        background: #1a1f35;
        border: 1px solid #3d5afe;
        border-radius: 10px;
        padding: 20px;
        margin-top: 10px;
    }
    .issue-badge {
        background: #f44336;
        color: white;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    .pass-badge {
        background: #4CAF50;
        color: white;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


# ── S3 loader ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_results_from_s3(bucket: str, prefix: str = "quality-results/") -> list:
    """Load all quality result JSONs from S3."""
    s3 = boto3.client("s3")
    results = []
    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        objects = response.get("Contents", [])
        # Sort by last modified, newest first
        objects = sorted(objects, key=lambda x: x["LastModified"], reverse=True)
        for obj in objects[:50]:  # Load latest 50
            data = s3.get_object(Bucket=bucket, Key=obj["Key"])
            result = json.loads(data["Body"].read().decode("utf-8"))
            results.append(result)
    except Exception as e:
        st.error(f"Error loading from S3: {e}")
    return results


def load_sample_data() -> list:
    """Sample data for demo/local testing."""
    return [
        {
            "filename": "hr_records_2024_01.csv",
            "passed": False,
            "total_issues": 3,
            "processed_at": "2024-11-01T10:23:00",
            "stats": {"total_rows": 15000, "total_columns": 12},
            "issues": [
                {"type": "NULL_VALUES", "column": "employee_id", "detail": "320 nulls (2.13% of rows)"},
                {"type": "DUPLICATE_ROWS", "column": "ALL", "detail": "45 duplicate rows found (0.3%)"},
                {"type": "OUTLIERS", "column": "salary", "detail": "12 outlier rows (Z-score > 3), range: [30000, 9500000]"}
            ],
            "ai_explanation": "**Summary:** Three data quality issues were detected in this HR dataset that could affect downstream reporting and payroll processing.\n\n**1. NULL_VALUES in employee_id:**\n- *Root cause:* Likely a data entry gap during onboarding batch import.\n- *Fix:* Cross-reference with the HR onboarding system and backfill missing IDs.\n\n**2. DUPLICATE_ROWS:**\n- *Root cause:* The ETL job may have run twice due to an EventBridge retry.\n- *Fix:* Add idempotency check using a composite key (employee_id + date) before inserting.\n\n**3. OUTLIERS in salary:**\n- *Root cause:* A data entry error — likely an extra zero added to some salary values.\n- *Fix:* Flag records where salary > $500K for manual review before loading to the warehouse."
        },
        {
            "filename": "retail_prices_2024_11.csv",
            "passed": True,
            "total_issues": 0,
            "processed_at": "2024-11-02T08:15:00",
            "stats": {"total_rows": 42000, "total_columns": 8},
            "issues": [],
            "ai_explanation": "✅ All data quality checks passed. No issues found."
        },
        {
            "filename": "transactions_2024_10.csv",
            "passed": False,
            "total_issues": 1,
            "processed_at": "2024-10-31T22:45:00",
            "stats": {"total_rows": 88500, "total_columns": 15},
            "issues": [
                {"type": "NULL_VALUES", "column": "transaction_amount", "detail": "1200 nulls (1.36% of rows)"}
            ],
            "ai_explanation": "**Summary:** Missing transaction amounts were detected, which could cause incorrect revenue calculations in downstream dashboards.\n\n**1. NULL_VALUES in transaction_amount:**\n- *Root cause:* Payment gateway API returned null for failed/pending transactions that weren't filtered out.\n- *Fix:* Add a pre-load filter to exclude transactions with status != 'COMPLETED' before writing to S3."
        }
    ]


# ── Header ────────────────────────────────────────────────────────────────────
st.title("🔍 AI-Powered Data Quality Monitor")
st.caption("Automated pipeline checks + Claude AI explanations for every data issue")
st.divider()

# ── Sidebar config ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")
    use_sample = st.toggle("Use sample data (demo mode)", value=True)
    if not use_sample:
        bucket_name = st.text_input("S3 Results Bucket", placeholder="your-dq-results-bucket")
        if st.button("🔄 Refresh Results"):
            st.cache_data.clear()
    st.divider()
    st.markdown("**Stack**")
    st.markdown("- AWS Lambda + S3 + EventBridge")
    st.markdown("- Python + pandas")
    st.markdown("- Claude API (Anthropic)")
    st.markdown("- Streamlit")

# ── Load data ─────────────────────────────────────────────────────────────────
if use_sample:
    results = load_sample_data()
else:
    if bucket_name:
        results = load_results_from_s3(bucket_name)
    else:
        st.warning("Enter your S3 bucket name in the sidebar.")
        st.stop()

if not results:
    st.info("No results found yet. Upload a CSV to your S3 input bucket to trigger the pipeline.")
    st.stop()

# ── Summary metrics ───────────────────────────────────────────────────────────
total = len(results)
passed = sum(1 for r in results if r["passed"])
failed = total - passed
total_issues = sum(r["total_issues"] for r in results)

col1, col2, col3, col4 = st.columns(4)
col1.metric("📁 Files Processed", total)
col2.metric("✅ Passed", passed, delta=f"{round(passed/total*100)}% pass rate")
col3.metric("❌ Failed", failed)
col4.metric("⚠️ Total Issues", total_issues)

st.divider()

# ── Results list ──────────────────────────────────────────────────────────────
st.subheader("📋 Pipeline Run Results")

for result in results:
    status_color = "pass-card" if result["passed"] else "fail-card"
    badge = f'<span class="pass-badge">PASSED</span>' if result["passed"] else f'<span class="issue-badge">{result["total_issues"]} ISSUES</span>'
    processed = result.get("processed_at", "")[:19].replace("T", " ")
    rows = result["stats"]["total_rows"]
    cols = result["stats"]["total_columns"]

    with st.expander(f"{'✅' if result['passed'] else '❌'}  {result['filename']}  —  {processed}  |  {rows:,} rows"):
        # File stats
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows", f"{rows:,}")
        c2.metric("Columns", cols)
        c3.metric("Issues Found", result["total_issues"])

        # Issues table
        if result["issues"]:
            st.markdown("**🔎 Issues Detected**")
            df_issues = pd.DataFrame(result["issues"])
            st.dataframe(df_issues, use_container_width=True, hide_index=True)

        # AI explanation
        st.markdown("**🤖 Claude AI Explanation**")
        st.markdown(
            f'<div class="ai-box">{result["ai_explanation"]}</div>',
            unsafe_allow_html=True
        )

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
st.caption("Built on top of aws-samples/aws-analytics-genai-llm-workshop · Extended with Lambda + Claude API + Streamlit")
