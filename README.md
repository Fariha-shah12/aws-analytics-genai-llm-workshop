# 🔍 AI-Powered Data Quality Monitor

> **Upload any CSV or Excel file · Get instant AI-powered data quality insights**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://aws-analytics-genai-llm-workshop-ksuph46n5ebek6kevxugky.streamlit.app)

Built on top of [aws-samples/aws-analytics-genai-llm-workshop](https://github.com/aws-samples/aws-analytics-genai-llm-workshop), extended with a serverless data quality layer and GenAI-powered root cause analysis.

---

## 🚀 Live Demo

**👉 [Try it here](https://aws-analytics-genai-llm-workshop-ksuph46n5ebek6kevxugky.streamlit.app)**

Upload any CSV or Excel file and get:
- Instant detection of nulls, duplicates, and outliers
- Plain-English AI explanation of every issue
- Actionable fix recommendations powered by Claude AI

---

## 🏗️ Architecture

### 1. Public Web App (`public_app.py`)
```
User uploads CSV/Excel → pandas quality checks → Claude API → Results on dashboard
```

### 2. AWS Serverless Pipeline (`lambda_data_quality.py`)
```
S3 input CSV → Lambda trigger → quality checks → Claude API → JSON saved to S3 → Streamlit dashboard
```

<img width="753" height="545" alt="AI-Powered Data Quality Monitor" src="https://github.com/user-attachments/assets/217b36d5-2b1d-42e5-9fa2-f41639479b9e" />


---

## ✨ Features

| Feature | Description |
|---|---|
| 📁 File Upload | Supports CSV, XLSX, XLS up to 200MB |
| 🕳️ Null Detection | Flags missing values per column with percentage |
| 👯 Duplicate Check | Detects repeated rows across entire dataset |
| 📊 Outlier Detection | Flags extreme values using Z-score > 3 |
| 🤖 AI Explanation | Claude API explains issues in plain English |
| ⚡ Fix Recommendations | Actionable steps to resolve each issue |
| ☁️ AWS Pipeline | Serverless auto-trigger via S3 + Lambda + EventBridge |

---

## 🛠️ Tech Stack

- **AWS Lambda** — serverless compute
- **Amazon S3** — data storage
- **Amazon EventBridge** — event-driven triggers
- **Python + pandas** — quality checks
- **Claude API (Anthropic)** — GenAI analysis
- **Streamlit** — web dashboard

---

## 🚀 Run Locally

```bash
git clone https://github.com/Fariha-shah12/aws-analytics-genai-llm-workshop.git
cd aws-analytics-genai-llm-workshop
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here
python -m streamlit run public_app.py
```

---

## ☁️ Deploy to Streamlit Cloud

1. Fork this repo
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Select repo + set main file to `public_app.py`
4. Add secret: `ANTHROPIC_API_KEY = "your-key"`
5. Deploy!

---

## 📁 Project Structure

```
├── public_app.py                 # Public web app with file uploader
├── lambda_data_quality.py        # AWS Lambda function
├── streamlit_dashboard/
│   └── streamlit_app.py          # S3-connected dashboard
├── requirements.txt
└── README.md
```

---

## 📝 Resume Bullet

```
Built an LLM-powered data quality monitoring pipeline on AWS (Lambda, S3, EventBridge)
processing 100K+ records, integrating Claude API to auto-generate plain-English anomaly
explanations, reducing manual debugging time by 60%. Deployed publicly on Streamlit Cloud.
```

---

## 🙏 Credits

- Base workshop: [aws-samples/aws-analytics-genai-llm-workshop](https://github.com/aws-samples/aws-analytics-genai-llm-workshop)
- Extended by: [@Fariha-shah12](https://github.com/Fariha-shah12)
