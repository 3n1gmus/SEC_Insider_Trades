import pandas as pd
import smtplib
import glob
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def load_recipients(filepath="recipients.txt"):
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found.")
        return []
    with open(filepath, "r") as f:
        return [line.strip() for line in f if line.strip()]

def generate_html_summary(csv_files):
    rows_html = ""
    
    for file in csv_files:
        df = pd.read_csv(file)
        
        # Sort by most insiders involved for maximum impact at the top
        df = df.sort_values(by="Insiders Count", ascending=False)
        
        for _, row in df.iterrows():
            op = str(row['Operation']).upper()
            color = "#28a745" if op == "BUY" else "#dc3545"
            val = f"${row['Net Value ($)']:,.2f}"
            
            # Use the new Ticker column
            ticker = row.get('Ticker', 'N/A')
            
            # Format insiders as a clean bulleted list
            insiders_list = str(row['Insiders Involved']).replace("; ", "<br>• ")
            
            rows_html += f"""
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 12px; vertical-align: top;">
                    <strong style="font-size: 16px;">{ticker}</strong><br>
                    <span style="font-size: 12px; color: #666;">{row['Company']}</span>
                </td>
                <td style="padding: 12px; vertical-align: top; color: {color}; font-weight: bold;">{op}</td>
                <td style="padding: 12px; vertical-align: top; text-align: center;">{row['Insiders Count']}</td>
                <td style="padding: 12px; vertical-align: top; text-align: right; font-family: monospace; font-weight: bold;">{val}</td>
                <td style="padding: 12px; font-size: 11px; color: #555; line-height: 1.4;">• {insiders_list}</td>
            </tr>
            """

    return f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f7f9;">
        <div style="max-width: 950px; margin: auto; background: white; padding: 25px; border-radius: 12px; border: 1px solid #e1e4e8; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <h2 style="color: #0366d6; border-bottom: 2px solid #0366d6; padding-bottom: 10px; margin-top: 0;">📊 Insider Cluster Intelligence</h2>
            <p style="color: #586069;">The following high-conviction clusters were detected by the SEC Insider Agent:</p>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead>
                    <tr style="background-color: #0366d6; color: white;">
                        <th style="padding: 12px; text-align: left; border-radius: 6px 0 0 0;">Entity</th>
                        <th style="padding: 12px; text-align: left;">Action</th>
                        <th style="padding: 12px; text-align: center;">Insiders</th>
                        <th style="padding: 12px; text-align: right;">Net Value</th>
                        <th style="padding: 12px; text-align: left; border-radius: 0 6px 0 0;">Participants</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
            
            <div style="margin-top: 30px; padding: 15px; background-color: #fffbdd; border: 1px solid #d1d5da; border-radius: 6px; font-size: 12px; color: #735c0f;">
                <strong>Note:</strong> This report focuses exclusively on C-Suite Officers and Directors. "Net Value" reflects the combined total of all detected trades in this window.
            </div>
            
            <footer style="margin-top: 30px; font-size: 11px; color: #999; text-align: center;">
                Sent via <strong>SEC_Insider_Trades GitHub Agent</strong>
            </footer>
        </div>
    </body>
    </html>
    """

def send_emails(html_content, recipients):
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_PASSWORD")
    
    if not sender or not password:
        print("Error: SMTP credentials missing.")
        return

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)

        for email in recipients:
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = email
            msg['Subject'] = "🚨 Insider Alert: High-Conviction Clusters Found"
            msg.attach(MIMEText(html_content, 'html'))
            server.send_message(msg)
            print(f"Sent successfully to {email}")
        
        server.quit()
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    csv_reports = glob.glob("analysis_of_*.csv")
    email_list = load_recipients("recipients.txt")

    if csv_reports and email_list:
        html = generate_html_summary(csv_reports)
        send_emails(html, email_list)
    else:
        if not csv_reports: print("No CSV reports found.")
        if not email_list: print("No recipients found in recipients.txt.")