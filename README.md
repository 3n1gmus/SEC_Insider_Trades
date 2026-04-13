# SEC_Insider_Trades
Python Scripts to get insider trading information

***

# 📊 SEC Insider Intelligence Agent

An automated end-to-end pipeline that monitors SEC filings, identifies "High-Conviction" insider clusters, and delivers a contextualized intelligence report with live market news.

## 🔄 The Data Pipeline

1.  **`Insider_Trade_Tracker.py` (The Harvester)** Scrapes the SEC EDGAR database for recent Form 4 filings. It extracts raw transaction data (insider names, roles, shares, and prices) and saves it as `insider_analysis.json`.

2.  **`FindExecutiveSentiments.py` (The Analyst)** Processes the raw JSON to find "Clusters." It filters for C-suite officers and directors, then identifies companies where multiple leaders are moving in the same direction. It outputs the consolidated `analysis_of_insider_analysis.csv`.

3.  **`report_processor.py` (The Intelligence Officer)** Converts the CSV into a professional HTML dashboard. It fetches live market headlines for each company via RSS to provide context (e.g., earnings beats, product launches) and emails the final report with raw data attached as a ZIP.

## 🚀 Key Features

- **Cluster Detection**: Flags companies where 2+ high-level insiders trade within the same window.
- **Sentiment Scoring**: Classifies clusters as **BUY** or **SELL** based on net dollar value.
- **Market Context Engine**: Automatically pulls the top 3 headlines for every flagged ticker to explain the "Why" behind the moves.
- **Automated Audit**: Every email includes a ZIP file containing the raw JSON and CSV logs for full transparency.

## 🛠 Setup & Configuration

### 1. Environment Variables
The following GitHub Secrets (or local `.env` variables) are required for the email engine:
- `SENDER_EMAIL`: Your Gmail address.
- `SENDER_PASSWORD`: A 16-character **Google App Password**.
- `RECEIVER_EMAIL`: The target address for the reports (or use `recipients.txt`).

### 2. Dependencies
```bash
pip install pandas feedparser
```

### 3. Execution Flow
To run the full pipeline manually:
```bash
python Insider_Trade_Tracker.py
python FindExecutiveSentiments.py
python report_processor.py
```

## 📅 Automation Schedule
The agent is configured via GitHub Actions to run **Tuesday through Saturday** at **07:00 UTC**, ensuring you receive a report after the SEC processing window closes for the previous day's filings.

```yaml
on:
  schedule:
    - cron: '0 7 * * 2-6'
```

## ⚠️ Disclaimer
This tool is for informational purposes only. Insider trading data is one of many indicators and should not be the sole basis for investment decisions. Use the provided "Market Context" to verify signals against broader economic news.