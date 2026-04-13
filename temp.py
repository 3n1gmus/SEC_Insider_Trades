import pandas as pd
import smtplib
import glob
import os
import zipfile
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

def load_recipients(filepath="recipients.txt"):
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found.")
        return []
    with open(filepath, "r") as f:
        return [line.strip() for line in f if line.strip()]

def create_data_zip(zip_name="insider_data_logs.zip"):
    """Zips all CSV and JSON files in the root directory."""
    files_to_zip = glob.glob("*.csv") + glob.glob("*.json")
    if not files_to_zip:
        return None
    
    with zipfile.ZipFile(zip_name, 'w') as zipf:
        for file in files_to_zip:
            zipf.write(file)
    return zip_name

def generate_html_summary(csv_files):
    rows_html = ""
    for file in csv_files:
        df = pd.read_csv(file)
        df = df.sort_values(by="Insiders Count", ascending=False)
        for _, row in df.iterrows():
            op = str(row['Operation']).upper()
            color = "#28a745" if op == "BUY" else "#dc3545"
            val = f"${row['Net Value ($)']:,.2f}"
            ticker = row.get('Ticker', 'N/A')
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
    # (HTML template remains the same as previous version)
    return f"<html>...{rows_html}...</html>" 

def send_emails(html_content, recipients, zip_path=None):
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
            msg['Subject'] = "🚨 Insider Alert: High-Conviction Clusters + Raw Data"
            
            # Attach HTML Body
            msg.attach(MIMEText(html_content, 'html'))
            
            # Attach Zip File
            if zip_path and os.path.exists(zip_path):
                with open(zip_path, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {zip_path}",
                )
                msg.attach(part)

            server.send_message(msg)
            print(f"Sent successfully to {email}")
        
        server.quit()
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    csv_reports = glob.glob("analysis_of_*.csv")
    email_list = load_recipients("recipients.txt")

    if csv_reports and email_list:
        # 1. Create Zip
        zip_filename = create_data_zip()
        
        # 2. Generate HTML
        html = generate_html_summary(csv_reports)
        
        # 3. Send
        send_emails(html, email_list, zip_path=zip_filename)
        
        # 4. Cleanup (Optional: remove zip after sending)
        if zip_filename and os.path.exists(zip_filename):
            os.remove(zip_filename)
    else:
        print("Missing reports or recipients.")