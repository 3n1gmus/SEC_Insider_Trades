#!/usr/bin/env python3
"""
sec_form4_search.py

Query SEC EDGAR JSON search API for Form 4 filings with date filtering
and save the raw results to a JSON file.
"""

import requests
import sys
import argparse
import json
from datetime import datetime

# SEC EFTS Search Endpoint
SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"

# IMPORTANT: The SEC requires a descriptive User-Agent
HEADERS = {
    "User-Agent": "walter schoenly wschoenly@tutanota.com",
    "Accept": "application/json",
}

def fetch_sec_data(params):
    """Executes the GET request to the SEC API."""
    response = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()

def save_to_file(data, filename):
    """Saves the dictionary data to a formatted JSON file."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print(f"\n[SUCCESS] Raw results saved to: {filename}")
    except IOError as e:
        print(f"[ERROR] Could not save file: {e}")

def main():
    parser = argparse.ArgumentParser(description="Search SEC Form 4 filings and save to JSON.")
    
    # Search parameters
    parser.add_argument("--query", default="form 4", help="Search query (default: 'form 4')")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument("--count", default="20", help="Number of results to return")
    parser.add_argument("--output", default="sec_results.json", help="Output filename")

    args = parser.parse_args()

    # Build params for the SEC EFTS API
    params = {
        "q": args.query,
        "filter_forms": "4",
        "count": args.count,
    }

    # Add date filters if provided
    # The SEC EFTS API uses 'startdt' and 'enddt' in YYYY-MM-DD format
    if args.start:
        params["startdt"] = args.start
    if args.end:
        params["enddt"] = args.end

    print(f"Searching SEC for: '{args.query}'...")
    if args.start or args.end:
        print(f"Date Range: {args.start or 'Beginning'} to {args.end or 'Present'}")

    try:
        json_data = fetch_sec_data(params)
        
        # Display high-level summary
        hits = json_data.get("hits", {}).get("total", {}).get("value", 0)
        print(f"Found approximately {hits} total matches.")
        
        # Save the full raw response
        save_to_file(json_data, args.output)

    except requests.HTTPError as e:
        print(f"HTTP error occurred: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()