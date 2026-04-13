import pandas as pd
import smtplib
import glob
import os
import zipfile
import feedparser
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

def get_market_context(ticker, company):
    """Fetches live headlines to provide context for the moves."""
    query = urllib.parse.quote(f"{ticker} {company} stock news earnings")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    
    feed = feedparser.parse(url)
    headlines = []
    
    for entry in feed.entries[:3]:
        title = entry.title.rsplit(' - ', 1)[0]
        headlines.append(f'• <a href="{entry.link}" style="color: #0366d6; text-decoration: none;">{title}</a>')
    
    return "<br>".join(headlines) if headlines else "<span style='color: #999;'>No recent headlines found.</span>"

def generate_html_summary(csv_files):
    rows_html = ""
    for file in csv_files:
        df = pd.read_csv(file)
        # Sort by impact: Net Value (absolute) so biggest money moves are at the top
        df['abs_val'] = df['Net Value ($)'].abs()
        df = df.sort_values(by="abs_val", ascending=False)
        
        for _, row in df.iterrows():
            op = str(row['Operation']).upper()
            color = "#28a745" if op == "BUY" else "#dc3545"
            
            # Formatted data from original CSV
            val_fmt = f"${row['Net Value ($)']:,.2f}"
            shares_fmt = f"{int(row['Net Shares']):,}"
            ticker = row.get('Ticker', 'N/A')
            company = row['Company']
            
            print(f"Generating context for {ticker}...")
            news_context = get_market_context(ticker, company)
            
            insiders_list = str(row['Insiders Involved']).replace("; ", "<br>• ")
            
            rows_html += f"""
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 15px; vertical-align: top; width: 150px;">
                    <strong style="font-size: 18px; color: #333;">{ticker}</strong><br>
                    <span style="font-size: 11px; color: #666; text-transform: uppercase;">{company}</span>
                </td>
                <td style="padding: 15px; vertical-align: top; color: {color}; font-weight: bold; text-align: center;">{op}</td>
                <td style="padding: 15px; vertical-align: top; text-align: center; font-size: 14px;">{row['Insiders Count']}</td>
                <td style="padding: 15px; vertical-align: top; text-align: right; font-family: monospace;">
                    <strong>{val_fmt}</strong><br>
                    <span style="font-size: 11px; color: #888;">{shares_fmt} Shares</span>
                </td>
                <td style="padding: 15px; font-size: 12px; color: #444; line-height: 1.5;">
                    <div style="margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px dashed #eee;">
                        <strong style="font-size: 10px; color: #999;">INSIDERS INVOLVED:</strong><br>
                        • {insiders_list}
                    </div>
                    <div style="background-color: #f0f7ff; padding: 10px; border-radius: 6px; border-left: 3px solid #0366d6;">
                        <strong style="font-size: 10px; color: #0366d6;">LIVE MARKET CONTEXT:</strong><br>
                        {news_context}
                    </div>
                </td>
            </tr>
            """

    return f"""
    <html>
    <body style="font-family: -apple-system, Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f7f9;">
        <div style="max-width: 1100px; margin: auto; background: white; padding: 30px; border-radius: 12px; border: 1px solid #e1e4e8;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #0366d6; padding-bottom: 10px;">
                <h2 style="color: #0366d6; margin: 0;">📊 Insider Intelligence Dashboard</h2>
                <span style="color: #666; font-size: 12px;">Original Data + Market Context</span>
            </div>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead>
                    <tr style="background-color: #f8f9fa; color: #555; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6;">Entity</th>
                        <th style="padding: 12px; text-align: center; border-bottom: 2px solid #dee2e6;">Action</th>
                        <th style="padding: 12px; text-align: center; border-bottom: 2px solid #dee2e6;">Count</th>
                        <th style="padding: 12px; text-align: right; border-bottom: 2px solid #dee2e6;">Net Value & Shares</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #dee2e6;">Participants & Context</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
            
            <p style="font-size: 11px; color: #999; margin-top: 30px; text-align: center;">
                Raw CSV and JSON files are attached to this email for your audit.
            </p>
        </div>
    </body>
    </html>
    """

# Helper functions: create_data_zip, load_recipients, and send_emails (as defined before)
def create_data_zip(zip_name="insider_data_audit.zip"):
    files = glob.glob("*.csv") + glob.glob("*.json")
    if not files: return None
    with zipfile.ZipFile(zip_name, 'w') as zipf:
        for file in files: zipf.write(file)
    return zip_name

def load_recipients(filepath="recipients.txt"):
    if not os.path.exists(filepath): return []
    with open(filepath, "r") as f: return [line.strip() for line in f if line.strip()]

def send_emails(html_content, recipients, zip_path=None):
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_PASSWORD")
    if not (sender and password): return
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)
        for email in recipients:
            msg = MIMEMultipart()
            msg['From'] = f"SEC Insider Agent <{sender}>"
            msg['To'] = email
            msg['Subject'] = "🚨 Insider Activity Intelligence Report"
            msg.attach(MIMEText(html_content, 'html'))
            if zip_path:
                with open(zip_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={zip_path}")
                msg.attach(part)
            server.send_message(msg)
        server.quit()
    except Exception as e: print(f"Email error: {e}")

if __name__ == "__main__":
    reports = glob.glob("analysis_of_*.csv")
    recipients = load_recipients("recipients.txt")
    if reports and recipients:
        audit_zip = create_data_zip()
        html = generate_html_summary(reports)
        send_emails(html, recipients, zip_path=audit_zip)
        if audit_zip: os.remove(audit_zip)