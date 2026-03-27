import requests
import json
import xml.etree.ElementTree as ET
import time
import argparse
from datetime import datetime, timedelta

# SEC SETTINGS
# Note: You MUST change this User-Agent to your own info or the SEC may block you.
HEADERS = {
    "User-Agent": "walter schoenly wschoenly@tutanota.com",
    "Accept": "application/json",
}
SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
BASE_DATA_URL = "https://www.sec.gov/Archives/edgar/data"

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
    """
    Parses Form 4 XML for BUY/SELL actions and the Insider's specific Job Title.
    """
    try:
        root = ET.fromstring(xml_content)
        
        # 1. Identity and Relationship
        owner_node = root.find(".//reportingOwnerId/rptOwnerName")
        owner_name = owner_node.text if owner_node is not None else "Unknown"
        
        rel = root.find(".//reportingOwnerRelationship")
        is_director = False
        officer_title = "N/A"
        
        if rel is not None:
            # Check Director status
            dir_node = rel.find("isDirector")
            if dir_node is not None and dir_node.text in ['1', 'true', 'True']:
                is_director = True
            
            # Extract Officer Title (e.g., "Chief Executive Officer")
            title_node = rel.find("officerTitle")
            if title_node is not None and title_node.text:
                officer_title = title_node.text
            elif is_director:
                officer_title = "Director"

        # 2. Extract Transactions
        transactions = []
        for trans in root.findall(".//nonDerivativeTransaction"):
            code_node = trans.find(".//transactionCoding/transactionCode")
            
            if code_node is not None:
                code = code_node.text
                if code in ['P', 'S']:
                    action = "BUY" if code == 'P' else "SELL"
                    date = trans.find(".//transactionDate/value").text
                    shares = trans.find(".//transactionShares/value").text
                    price = trans.find(".//transactionPricePerShare/value").text
                    
                    transactions.append({
                        "action": action,
                        "date": date,
                        "shares": float(shares) if shares else 0,
                        "price_per_share": float(price) if price else 0,
                        "total_value": (float(shares) if shares else 0) * (float(price) if price else 0)
                    })
        
        if not transactions:
            return None

        return {
            "insider_name": owner_name,
            "role": officer_title,  # <--- New field added here
            "is_on_board": is_director,
            "transactions": transactions
        }
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(description="Analyze SEC Insider Trading (Buys & Sales)")
    parser.add_argument("--days", type=int, default=30, help="Number of days to look back")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=50, help="Max filings to analyze")
    args = parser.parse_args()

    end_date = args.end if args.end else datetime.now().strftime('%Y-%m-%d')
    start_date = args.start if args.start else (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')

    print(f"[*] Searching for Form 4s from {start_date} to {end_date}...")

    params = {
        "q": "form 4",
        "filter_forms": "4",
        "startdt": start_date,
        "enddt": end_date,
        "count": args.limit
    }

    try:
        search_resp = requests.get(SEARCH_URL, params=params, headers=HEADERS)
        search_resp.raise_for_status()
        hits = search_resp.json().get('hits', {}).get('hits', [])
    except Exception as e:
        print(f"Search failed: {e}")
        return

    results = []
    print(f"[*] Found {len(hits)} filings. Extracting details...")

    for hit in hits:
        source = hit['_source']
        adsh = source['adsh']
        cik = source['ciks'][0]
        company = source['display_names'][0]

        xml_text = get_filing_xml(cik, adsh)
        if xml_text:
            data = parse_form4_xml(xml_text)
            if data:
                data['company_name'] = company
                data['accession_number'] = adsh
                results.append(data)
                
                # Dynamic terminal output for visual confirmation
                for t in data['transactions']:
                    print(f"  [+] {t['action']} by {data['insider_name']} ({company}) - {t['shares']} shares")
        
        # Respect SEC rate limits (10/sec)
        time.sleep(0.11)

    output_file = "insider_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=4)

    print(f"\n[!] Analysis Complete. Compiled {len(results)} records into {output_file}")

if __name__ == "__main__":
    main()