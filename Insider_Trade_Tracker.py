# pip install requests

import requests
import json
import xml.etree.ElementTree as ET
import time
import argparse
from datetime import datetime, timedelta

# SEC SETTINGS
HEADERS = {
    "User-Agent": "walter schoenly wschoenly@tutanota.com",
    "Accept": "application/json",
}
SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
BASE_DATA_URL = "https://www.sec.gov/Archives/edgar/data"

# --- CONFIGURABLE TIMEOUTS ---
RETRY_BACKOFF = 5  # Base seconds to wait on a 500 error
MAX_RETRIES = 3    # Number of times to attempt a request before giving up
SEC_RATE_LIMIT = 0.11 # 10 requests per second is the SEC limit; 0.11 provides a safety buffer

def get_filing_xml(cik, adsh):
    adsh_clean = adsh.replace('-', '')
    xml_url = f"{BASE_DATA_URL}/{cik}/{adsh_clean}/form4.xml"
    try:
        resp = requests.get(xml_url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None

def parse_form4_xml(xml_content):
    try:
        root = ET.fromstring(xml_content)
        issuer_node = root.find(".//issuer/issuerName")
        actual_company = issuer_node.text if issuer_node is not None else "Unknown"
        owner_node = root.find(".//reportingOwnerId/rptOwnerName")
        owner_name = owner_node.text if owner_node is not None else "Unknown"
        rel = root.find(".//reportingOwnerRelationship")
        is_director = False
        officer_title = "N/A"
        if rel is not None:
            dir_node = rel.find("isDirector")
            if dir_node is not None and dir_node.text in ['1', 'true', 'True']:
                is_director = True
            title_node = rel.find("officerTitle")
            if title_node is not None and title_node.text:
                officer_title = title_node.text
            elif is_director:
                officer_title = "Director"

        transactions = []
        for trans in root.findall(".//nonDerivativeTransaction"):
            code_node = trans.find(".//transactionCoding/transactionCode")
            if code_node is not None and code_node.text in ['P', 'S']:
                action = "BUY" if code_node.text == 'P' else "SELL"
                date_node = trans.find(".//transactionDate/value")
                shares_node = trans.find(".//transactionShares/value")
                price_node = trans.find(".//transactionPricePerShare/value")
                
                if date_node is not None and shares_node is not None:
                    shares = float(shares_node.text) if shares_node.text else 0
                    price = float(price_node.text) if price_node and price_node.text else 0
                    transactions.append({
                        "action": action,
                        "date": date_node.text,
                        "shares": shares,
                        "price_per_share": price,
                        "total_value": round(shares * price, 2)
                    })
        
        if not transactions: return None
        return {"insider_name": owner_name, "company_name": actual_company, "role": officer_title, "is_on_board": is_director, "transactions": transactions}
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(description="SEC Insider Analyzer (Robust Edition)")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=200, help="0 for unlimited")
    args = parser.parse_args()

    end_date = args.end if args.end else datetime.now().strftime('%Y-%m-%d')
    start_date = args.start if args.start else (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')

    print(f"[*] Scanning from {start_date} to {end_date}...")
    
    results = []
    start_from = 0
    page_size = 100

    while True:
        if args.limit != 0 and len(results) >= args.limit: break

        params = {"q": "form 4", "filter_forms": "4", "startdt": start_date, "enddt": end_date, "from": start_from, "count": page_size}
        
        # --- IMPROVED RETRY LOGIC ---
        hits = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=15)
                if resp.status_code == 200:
                    hits = resp.json().get('hits', {}).get('hits', [])
                    break
                elif resp.status_code == 500:
                    wait_time = RETRY_BACKOFF * (attempt + 1)
                    print(f"  [!] SEC Server Error (500). Retrying in {wait_time}s (Attempt {attempt + 1}/{MAX_RETRIES})...")
                    time.sleep(wait_time)
                else:
                    print(f"  [!] Unexpected Status {resp.status_code}. Retrying...")
                    time.sleep(2)
            except Exception as e:
                print(f"  [!] Connection error: {e}. Retrying...")
                time.sleep(2)
        
        if hits is None:
            print("[!] SEC Search is down or unresponsive. Saving progress and exiting.")
            break
        if not hits:
            print("[*] No more filings found.")
            break

        for hit in hits:
            if args.limit != 0 and len(results) >= args.limit: break
            source = hit['_source']
            xml = get_filing_xml(source['ciks'][0], source['adsh'])
            if xml:
                data = parse_form4_xml(xml)
                if data:
                    data['accession_number'] = source['adsh']
                    results.append(data)
                    print(f"  [+] {data['transactions'][0]['action']} - {data['insider_name']} ({data['company_name']})")
            time.sleep(SEC_RATE_LIMIT) 

        start_from += page_size

    with open("insider_analysis.json", 'w') as f:
        json.dump(results, f, indent=4)
    print(f"\n[!] Success. Compiled {len(results)} records.")

if __name__ == "__main__":
    main()