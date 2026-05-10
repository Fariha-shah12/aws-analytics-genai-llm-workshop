import streamlit as st
import pandas as pd
import json
import os
import urllib3
from datetime import datetime

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Data Quality Monitor",
    page_icon="🔍",
    layout="wide"
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@300;400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .stApp {
        background: #0a0e1a;
    }

    .hero-title {
        font-family: 'Space Mono', monospace;
        font-size: 2.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #00d4ff, #7b2fff, #ff6b6b);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }

    .hero-sub {
        color: #6b7a99;
        font-size: 1rem;
        font-weight: 300;
        letter-spacing: 0.05em;
        margin-bottom: 2rem;
    }

    .upload-zone {
        border: 2px dashed #2a3350;
        border-radius: 16px;
        padding: 3rem;
        text-align: center;
        background: #111827;
        transition: border-color 0.3s;
        margin-bottom: 2rem;
    }

    .metric-card {
        background: #111827;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #1e2a45;
        text-align: center;
    }

    .metric-number {
        font-family: 'Space Mono', monospace;
        font-size: 2.5rem;
        font-weight: 700;
        color: #00d4ff;
    }

    .metric-label {
        color: #6b7a99;
        font-size: 0.8rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }

    .issue-card {
        background: #111827;
        border-radius: 12px;
        padding: 1.5rem;
        border-left: 4px solid #ff6b6b;
        margin-bottom: 1rem;
    }

    .pass-card {
        background: #111827;
        border-radius: 12px;
        padding: 1.5rem;
        border-left: 4px solid #00d4ff;
        margin-bottom: 1rem;
    }

    .ai-box {
        background: linear-gradient(135deg, #0d1225, #111827);
        border: 1px solid #2a3350;
        border-radius: 16px;
        padding: 2rem;
        margin-top: 1.5rem;
        position: relative;
    }

    .ai-badge {
        display: inline-block;
        background: linear-gradient(135deg, #7b2fff, #00d4ff);
        color: white;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        padding: 4px 12px;
        border-radius: 20px;
        margin-bottom: 1rem;
    }

    .tag {
        display: inline-block;
        background: #1e2a45;
        color: #00d4ff;
        font-size: 0.75rem;
        padding: 3px 10px;
        border-radius: 20px;
        margin-right: 6px;
        font-family: 'Space Mono', monospace;
    }

    .tag-fail {
        background: #2a1e1e;
        color: #ff6b6b;
    }

    .section-header {
        font-family: 'Space Mono', monospace;
        font-size: 1rem;
        color: #00d4ff;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        margin-bottom: 1rem;
        border-bottom: 1px solid #1e2a45;
        padding-bottom: 0.5rem;
    }

    div[data-testid="stFileUploader"] {
        background: #111827;
        border-radius: 12px;
        border: 2px dashed #2a3350;
        padding: 1rem;
    }

    .footer {
        text-align: center;
        color: #2a3350;
        font-size: 0.75rem;
        margin-top: 4rem;
        padding-top: 2rem;
        border-top: 1px solid #1e2a45;
        font-family: 'Space Mono', monospace;
    }
</style>
""", unsafe_allow_html=True)

http = urllib3.PoolManager()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


# ── Quality checks ────────────────────────────────────────────────────────────
def run_quality_checks(df: pd.DataFrame, filename: str) -> dict:
    issues = []
    stats = {}
    total_rows = len(df)
    total_cols = len(df.columns)
    stats["total_rows"] = total_rows
    stats["total_columns"] = total_cols

    # Null checks
    null_counts = df.isnull().sum()
    null_pct = (null_counts / total_rows * 100).round(2)
    for col, count in null_counts[null_counts > 0].items():
        issues.append({"type": "NULL_VALUES", "column": col,
                       "detail": f"{count} nulls ({null_pct[col]}% of rows)"})

    # Duplicate check
    dup_count = df.duplicated().sum()
    if dup_count > 0:
        issues.append({"type": "DUPLICATE_ROWS", "column": "ALL",
                       "detail": f"{dup_count} duplicate rows ({round(dup_count/total_rows*100, 2)}%)"})

    # Outlier check
    for col in df.select_dtypes(include=["number"]).columns:
        mean, std = df[col].mean(), df[col].std()
        if std > 0:
            outliers = df[(df[col] - mean).abs() > 3 * std]
            if len(outliers) > 0:
                issues.append({"type": "OUTLIERS", "column": col,
                               "detail": f"{len(outliers)} outliers (Z>3), range [{df[col].min():.1f}, {df[col].max():.1f}]"})

    stats["column_types"] = df.dtypes.astype(str).to_dict()
    stats["null_pct"] = null_pct.to_dict()

    return {
        "filename": filename,
        "passed": len(issues) == 0,
        "total_issues": len(issues),
        "issues": issues,
        "stats": stats,
        "processed_at": datetime.utcnow().isoformat()
    }


# ── Claude API ────────────────────────────────────────────────────────────────
def explain_with_claude(report: dict) -> str:
    if report["passed"]:
        return "✅ All checks passed! Your data looks clean and ready for analysis."

    issues_text = "\n".join([
        f"- [{i['type']}] Column '{i['column']}': {i['detail']}"
        for i in report["issues"]
    ])

    prompt = f"""You are a friendly data quality analyst helping a non-technical user understand their data issues.

File: '{report['filename']}' ({report['stats']['total_rows']} rows, {report['stats']['total_columns']} columns)

Issues found:
{issues_text}

Please provide:
1. **Plain-English Summary** — What went wrong in 2-3 simple sentences anyone can understand
2. **Root Cause** — For each issue, what likely caused it
3. **How to Fix It** — Simple, actionable steps for each issue

Be friendly, clear, and concise. Use bullet points."""

    try:
        response = http.request(
            "POST",
            "https://api.anthropic.com/v1/messages",
            body=json.dumps({
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01"
            }
        )
        result = json.loads(response.data.decode("utf-8"))
        if "content" in result:
            return result["content"][0]["text"]
        return f"AI explanation unavailable: {result.get('error', {}).get('message', 'Unknown error')}"
    except Exception as e:
        return f"Could not reach AI service: {str(e)}"


# ── UI ────────────────────────────────────────────────────────────────────────
st.markdown('<div class="hero-title">🔍 AI Data Quality Monitor</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Upload any CSV or Excel file · Get instant AI-powered data quality insights</div>', unsafe_allow_html=True)

# Upload
uploaded_file = st.file_uploader(
    "Drop your CSV or Excel file here",
    type=["csv", "xlsx", "xls"],
    help="Your file is analyzed locally — nothing is stored or shared."
)

if not uploaded_file:
    st.markdown("""
    <div style="text-align:center; padding: 3rem; color: #2a3350;">
        <div style="font-size: 3rem">📂</div>
        <div style="font-family: 'Space Mono', monospace; font-size: 0.9rem; margin-top: 1rem;">
            Upload a file above to get started
        </div>
        <div style="font-size: 0.8rem; margin-top: 0.5rem; color: #1e2a45;">
            Supports CSV, XLSX, XLS · Max 200MB
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="margin-top: 3rem;">
        <div class="section-header">What this tool checks</div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; margin-top: 1rem;">
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""<div class="metric-card">
            <div style="font-size:2rem">🕳️</div>
            <div style="color:#00d4ff; font-weight:600; margin-top:0.5rem">Missing Values</div>
            <div style="color:#6b7a99; font-size:0.85rem">Detects null/empty cells per column</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""<div class="metric-card">
            <div style="font-size:2rem">👯</div>
            <div style="color:#00d4ff; font-weight:600; margin-top:0.5rem">Duplicate Rows</div>
            <div style="color:#6b7a99; font-size:0.85rem">Finds repeated records in your data</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown("""<div class="metric-card">
            <div style="font-size:2rem">📊</div>
            <div style="color:#00d4ff; font-weight:600; margin-top:0.5rem">Outliers</div>
            <div style="color:#6b7a99; font-size:0.85rem">Flags extreme values using Z-score</div>
        </div>""", unsafe_allow_html=True)

else:
    # Read file
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Could not read file: {e}")
        st.stop()

    # Run checks
    with st.spinner("🔍 Analyzing your data..."):
        report = run_quality_checks(df, uploaded_file.name)

    # Run Claude
    with st.spinner("🤖 Getting AI explanation..."):
        explanation = explain_with_claude(report)

    # Results header
    status_color = "#00d4ff" if report["passed"] else "#ff6b6b"
    status_text = "✅ PASSED" if report["passed"] else "❌ ISSUES FOUND"
    st.markdown(f"""
    <div style="background:#111827; border-radius:12px; padding:1.5rem; 
                border-left: 4px solid {status_color}; margin-bottom:2rem;">
        <span style="font-family:'Space Mono',monospace; color:{status_color}; font-size:1.2rem; font-weight:700;">
            {status_text}
        </span>
        <span style="color:#6b7a99; margin-left:1rem; font-size:0.9rem;">
            {uploaded_file.name}
        </span>
    </div>
    """, unsafe_allow_html=True)

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-number">{report["stats"]["total_rows"]:,}</div><div class="metric-label">Total Rows</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-number">{report["stats"]["total_columns"]}</div><div class="metric-label">Columns</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-number" style="color:{"#ff6b6b" if report["total_issues"] > 0 else "#00d4ff"}">{report["total_issues"]}</div><div class="metric-label">Issues Found</div></div>', unsafe_allow_html=True)
    with c4:
        null_cols = sum(1 for v in report["stats"]["null_pct"].values() if v > 0)
        st.markdown(f'<div class="metric-card"><div class="metric-number">{null_cols}</div><div class="metric-label">Columns w/ Nulls</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Issues table
    if report["issues"]:
        st.markdown('<div class="section-header">Issues Detected</div>', unsafe_allow_html=True)
        df_issues = pd.DataFrame(report["issues"])
        df_issues.columns = ["Type", "Column", "Detail"]
        st.dataframe(df_issues, use_container_width=True, hide_index=True)

    # AI Explanation
    st.markdown('<div class="section-header" style="margin-top:2rem">Claude AI Explanation</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="ai-box">
        <div class="ai-badge">✦ Powered by Claude AI</div>
        <div style="color:#c8d6f0; line-height:1.8; font-size:0.95rem;">
            {explanation.replace(chr(10), '<br>')}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Data preview
    with st.expander("📋 Preview your data"):
        st.dataframe(df.head(20), use_container_width=True)

    # Schema
    with st.expander("🗂️ Column schema"):
        schema_df = pd.DataFrame({
            "Column": list(report["stats"]["column_types"].keys()),
            "Type": list(report["stats"]["column_types"].values()),
            "Null %": [f"{report['stats']['null_pct'].get(col, 0):.1f}%" 
                      for col in report["stats"]["column_types"].keys()]
        })
        st.dataframe(schema_df, use_container_width=True, hide_index=True)

# Footer
st.markdown("""
<div class="footer">
    Built with AWS Lambda · S3 · Claude API · Streamlit &nbsp;·&nbsp; 
    <a href="https://github.com/Fariha-shah12/aws-analytics-genai-llm-workshop" 
       style="color:#2a3350; text-decoration:none;">View on GitHub</a>
</div>
""", unsafe_allow_html=True)
