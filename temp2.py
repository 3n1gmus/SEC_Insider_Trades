#!/usr/bin/env python3
# pip install requests
"""
sec_insider_analyzer.py

1. Searches SEC for Form 4 filings (default last 30 days).
2. Fetches the underlying XML for each filing.
3. Extracts: Who bought, Board status, Amount, and Date.
4. Saves everything to 'insider_analysis.json'.

Usage:
    python sec_insider_analyzer.py --days 60
    python sec_insider_analyzer.py --start 2024-01-01 --end 2024-01-31
"""

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
    """Fetches the XML content of a specific Form 4 filing."""
    adsh_clean = adsh.replace('-', '')
    # The standard path for modern Form 4 XML data
    xml_url = f"{BASE_DATA_URL}/{cik}/{adsh_clean}/form4.xml"
    
    try:
        resp = requests.get(xml_url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None

def parse_form4_xml(xml_content):
    """Parses Form 4 XML for specific transaction and relationship data."""
    try:
        root = ET.fromstring(xml_content)
        
        # 1. Identity and Relationship
        owner_node = root.find(".//reportingOwnerId/rptOwnerName")
        owner_name = owner_node.text if owner_node is not None else "Unknown"
        
        rel = root.find(".//reportingOwnerRelationship")
        is_director = False
        if rel is not None:
            dir_node = rel.find("isDirector")
            # SEC uses '1' or 'true' for boolean True
            if dir_node is not None and dir_node.text in ['1', 'true', 'True']:
                is_director = True

        # 2. Extract Purchases (Transaction Code 'P')
        purchases = []
        for trans in root.findall(".//nonDerivativeTransaction"):
            code_node = trans.find(".//transactionCoding/transactionCode")
            
            # We only care about 'P' (Open market or private purchase)
            if code_node is not None and code_node.text == 'P':
                date = trans.find(".//transactionDate/value").text
                shares = trans.find(".//transactionShares/value").text
                price = trans.find(".//transactionPricePerShare/value").text
                
                purchases.append({
                    "date": date,
                    "shares": float(shares) if shares else 0,
                    "price_per_share": float(price) if price else 0,
                    "total_cost": (float(shares) if shares else 0) * (float(price) if price else 0)
                })
        
        # Only return if we found actual purchases
        if not purchases:
            return None

        return {
            "insider_name": owner_name,
            "is_on_board": is_director,
            "transactions": purchases
        }
    except Exception as e:
        return None

def main():
    parser = argparse.ArgumentParser(description="Analyze SEC Insider Trading")
    parser.add_argument("--days", type=int, default=30, help="Number of days to look back (default 30)")
    parser.add_argument("--start", help="Start date YYYY-MM-DD (overrides --days)")
    parser.add_argument("--end", help="End date YYYY-MM-DD (default today)")
    parser.add_argument("--limit", type=int, default=50, help="Max number of filings to analyze")
    args = parser.parse_args()

    # Calculate Date Range
    end_date = args.end if args.end else datetime.now().strftime('%Y-%m-%d')
    if args.start:
        start_date = args.start
    else:
        start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')

    print(f"[*] Searching for Form 4s from {start_date} to {end_date}...")

    # Step 1: Search the Index
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

    # Step 2: Deep-Dive into each Result
    results = []
    print(f"[*] Found {len(hits)} filings. Extracting details...")

    for hit in hits:
        source = hit['_source']
        adsh = source['adsh']
        # Use the first CIK (Reporting Owner)
        cik = source['ciks'][0]
        company = source['display_names'][0]

        # Get and parse XML
        xml_text = get_filing_xml(cik, adsh)
        if xml_text:
            data = parse_form4_xml(xml_text)
            if data:
                data['company_name'] = company
                data['accession_number'] = adsh
                results.append(data)
                print(f"  [+] Found purchase by {data['insider_name']} ({company})")
        
        # SEC rate limit is 10 requests/sec. We wait a bit to be safe.
        time.sleep(0.11)

    # Step 3: Save to JSON
    output_file = "insider_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=4)

    print(f"\n[!] Analysis Complete. Compiled {len(results)} purchases into {output_file}")

if __name__ == "__main__":
    main()