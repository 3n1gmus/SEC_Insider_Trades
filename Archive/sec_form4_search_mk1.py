#!/usr/bin/env python3
# pip install requests
"""
sec_form4_search.py

Query SEC EDGAR JSON search API for Form 4 filings and print raw/parsed results
so you can inspect the actual JSON shape when fields are missing.

Required pip install:
    pip install requests
"""

import requests
import sys
import argparse
import json

SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
HEADERS = {
    "User-Agent": "walter schoenly wschoenly@tutanota.com",
    "Accept": "application/json",
}
DEFAULT_PARAMS = {
    "q": "form 4",
    "filter_forms": "4",
    "page": "1",
    "count": "20",
}


def fetch(params):
    resp = requests.get(SEARCH_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp


def print_inspect(resp):
    data = resp.json()
    # Print top-level keys and a compact preview
    print("Top-level keys:", list(data.keys()))
    print("Total results (raw):", data.get("total") or data.get("hits") or data.get("hitsTotal") or "unknown")
    # Try common hit locations
    hits_candidates = []
    if "hits" in data and isinstance(data["hits"], list):
        hits_candidates = data["hits"]
    elif "hits" in data and isinstance(data["hits"], dict) and "hits" in data["hits"]:
        hits_candidates = data["hits"]["hits"]
    elif "results" in data:
        hits_candidates = data["results"]
    elif "data" in data:
        hits_candidates = data["data"]
    else:
        # fallback: attempt to find the largest list value
        lists = [(k, v) for k, v in data.items() if isinstance(v, list)]
        if lists:
            # choose the longest list found
            hits_candidates = max(lists, key=lambda t: len(t[1]))[1]

    if not hits_candidates:
        print("No obvious hits array found; printing full JSON for inspection:")
        print(json.dumps(data, indent=2)[:10000])
        return

    # Print a compact inspect of the first few items so you can see the actual keys/structure
    for i, raw_item in enumerate(hits_candidates[:5], 1):
        print("\n--- ITEM", i, "raw type:", type(raw_item).__name__, "---")
        # If item is a string that contains JSON, try to parse; otherwise show string length
        if isinstance(raw_item, str):
            try:
                parsed = json.loads(raw_item)
                print("String parsed as JSON; keys:", list(parsed.keys()))
                print(json.dumps(parsed, indent=2)[:4000])
            except Exception:
                print("String (non-JSON) preview:", raw_item[:1000])
        elif isinstance(raw_item, dict):
            print("Keys:", list(raw_item.keys()))
            # show a pretty-printed snippet of the dict
            print(json.dumps(raw_item, indent=2)[:4000])
        else:
            print("Item repr:", repr(raw_item)[:1000])


def main():
    parser = argparse.ArgumentParser(description="Inspect SEC EDGAR (Form 4) JSON response shape.")
    parser.add_argument("--query", default=DEFAULT_PARAMS["q"])
    parser.add_argument("--page", default=DEFAULT_PARAMS["page"])
    parser.add_argument("--count", default=DEFAULT_PARAMS["count"])
    args = parser.parse_args()

    params = {
        "q": args.query,
        "filter_forms": "4",
        "page": str(args.page),
        "count": str(args.count),
    }

    try:
        resp = fetch(params)
        print_inspect(resp)
    except requests.HTTPError as e:
        print("HTTP error:", e, file=sys.stderr)
        if e.response is not None:
            print(e.response.text[:5000], file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print("Request failed:", e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
