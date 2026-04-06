# pip install requests
import requests
import json
import xml.etree.ElementTree as ET
import time
import argparse
from datetime import datetime, timedelta
import re

# SEC SETTINGS
HEADERS = {
    "User-Agent": "walter schoenly wschoenly@tutanota.com",
    "Accept": "application/json",
}
SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
BASE_DATA_URL = "https://www.sec.gov/Archives/edgar/data"

RETRY_BACKOFF = 5 
MAX_RETRIES = 3    
SEC_RATE_LIMIT = 0.11 

session = requests.Session()
session.headers.update(HEADERS)

def safe_extract(node, path, is_float=False):
    """Safely extracts text or float from an XML path."""
    target = node.find(path)
    if target is not None and target.text:
        if is_float:
            try:
                return float(target.text)
            except ValueError:
                return 0.0
        return target.text
    return 0.0 if is_float else "N/A"

def get_filing_xml(cik, adsh):
    adsh_clean = adsh.replace('-', '')
    xml_url = f"{BASE_DATA_URL}/{cik}/{adsh_clean}/form4.xml"
    
    # Try up to 3 times if it times out
    for attempt in range(3):
        try:
            # Increased timeout to 20 seconds
            resp = session.get(xml_url, timeout=20) 
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code == 429: # Too many requests
                time.sleep(2) # Back off if throttled
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < 2:
                time.sleep(1) # Wait a second before trying again
                continue
            else:
                print(f"      [!] XML Fetch Error: Timeout after 3 attempts for {adsh}")
        except Exception as e:
            print(f"      [!] XML Fetch Error: {e}")
            break
    return None

def parse_form4_xml(xml_content):
    try:
        root = ET.fromstring(xml_content)
        
        # Meta Info - ADDED TICKER EXTRACTION HERE
        company = safe_extract(root, ".//issuer/issuerName")
        ticker = safe_extract(root, ".//issuer/issuerTradingSymbol")
        owner = safe_extract(root, ".//reportingOwnerId/rptOwnerName")
        
        rel = root.find(".//reportingOwnerRelationship")
        is_director = False
        officer_title = "N/A"
        if rel is not None:
            is_director = safe_extract(rel, "isDirector") in ['1', 'true', 'True']
            officer_title = safe_extract(rel, "officerTitle")
            if officer_title == "N/A" and is_director:
                officer_title = "Director"

        # Build Footnote Map
        footnotes = {}
        for fn in root.findall(".//footnotes/footnote"):
            fn_id = fn.get('id')
            if fn_id:
                footnotes[fn_id] = fn.text

        transactions = []
        for trans in root.findall(".//nonDerivativeTransaction"):
            code = safe_extract(trans, ".//transactionCoding/transactionCode")
            
            if code in ['P', 'S']:
                action = "BUY" if code == 'P' else "SELL"
                date = safe_extract(trans, ".//transactionDate/value")
                shares = safe_extract(trans, ".//transactionShares/value", is_float=True)
                price = safe_extract(trans, ".//transactionPricePerShare/value", is_float=True)
                
                if price == 0:
                    price_fn_node = trans.find(".//transactionPricePerShare/footnoteId")
                    if price_fn_node is not None:
                        fn_id = price_fn_node.get('id')
                        fn_text = footnotes.get(fn_id, "")
                        match = re.search(r'\$(\d+\.\d+)', fn_text)
                        if match:
                            price = float(match.group(1))

                if price > 0:
                    transactions.append({
                        "action": action,
                        "date": date,
                        "shares": shares,
                        "price_per_share": price,
                        "total_value": round(shares * price, 2)
                    })
        
        if not transactions: return None
        
        # ADDED TICKER TO RETURN DICTIONARY
        return {
            "ticker": ticker,
            "insider_name": owner, 
            "company_name": company, 
            "role": officer_title, 
            "is_on_board": is_director, 
            "transactions": transactions
        }
    except Exception as e:
        print(f"      [!] XML Parse Error: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="SEC Insider Analyzer")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    end_date = args.end if args.end else datetime.now().strftime('%Y-%m-%d')
    start_date = args.start if args.start else (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')

    print(f"[*] Scanning SEC for Form 4s: {start_date} to {end_date}...")
    
    results = []
    start_from = 0
    page_size = 100

    while True:
        if args.limit != 0 and len(results) >= args.limit: break

        params = {"q": "form 4", "filter_forms": "4", "startdt": start_date, "enddt": end_date, "from": start_from, "count": page_size}
        
        hits = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = session.get(SEARCH_URL, params=params, timeout=15)
                if resp.status_code == 200:
                    hits = resp.json().get('hits', {}).get('hits', [])
                    break
                time.sleep(RETRY_BACKOFF * (attempt + 1))
            except Exception:
                time.sleep(2)
        
        if not hits: break

        for hit in hits:
            if args.limit != 0 and len(results) >= args.limit: break
            cik = hit['_source']['ciks'][0]
            adsh = hit['_source']['adsh']
            
            xml = get_filing_xml(cik, adsh)
            if xml:
                data = parse_form4_xml(xml)
                if data:
                    data['accession_number'] = adsh
                    results.append(data)
                    t = data['transactions'][0]
                    # UPDATED PRINT STATEMENT TO SHOW TICKER
                    print(f"  [+] {data['ticker']:<6} | {t['action']} | ${t['price_per_share']:>8.2f} | {data['insider_name'][:20]:<20}")
            
            time.sleep(SEC_RATE_LIMIT) 

        start_from += page_size

    with open("insider_analysis.json", 'w') as f:
        json.dump(results, f, indent=4)
    print(f"\n[!] Success. Saved {len(results)} records to insider_analysis.json")

if __name__ == "__main__":
    main()