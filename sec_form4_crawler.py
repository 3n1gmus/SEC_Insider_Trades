#!/usr/bin/env python3
"""
SEC Form 4 crawler with CLI date options.

Usage examples:
  python sec_form4_crawler.py                 # last 30 days (default)
  python sec_form4_crawler.py --days-back 7
  python sec_form4_crawler.py --start 2026-01-01 --end 2026-01-31
  python sec_form4_crawler.py --start 2026-01-01 --days-back 10  # start wins if provided

Options:
  --start YYYY-MM-DD     Explicit start date (inclusive)
  --end YYYY-MM-DD       Explicit end date (inclusive)
  --days-back N          Fetch filings from last N days (default 30)
  --output DIR           Output directory (default "sec_form4s")
  --page-size N          Search page size (default 100)
  --delay FLOAT          Seconds between requests (default 0.25)
  --max-pages N          Limit number of pages crawled (for testing)
  --only-xml             Save only .xml filing documents (machine-readable)
  --user-agent STR       Custom User-Agent (required by SEC; override default)
"""
import os
import re
import time
import math
import argparse
import requests
from urllib.parse import urljoin, urlencode
from datetime import datetime, timedelta
from lxml import html

# SEC endpoints
SEARCH_BASE = "https://efts.sec.gov/LATEST/search-index"
EDGAR_BASE = "https://www.sec.gov"

def parse_args():
    p = argparse.ArgumentParser(description="Download Form 4 filings from SEC EDGAR")
    p.add_argument("--start", help="Start date YYYY-MM-DD (inclusive)", default=None)
    p.add_argument("--end", help="End date YYYY-MM-DD (inclusive)", default=None)
    p.add_argument("--days-back", type=int, help="Days back from today (used if start/end not provided)", default=30)
    p.add_argument("--output", help="Output directory", default="sec_form4s")
    p.add_argument("--page-size", type=int, help="Search page size (max 100)", default=100)
    p.add_argument("--delay", type=float, help="Seconds between requests", default=0.25)
    p.add_argument("--max-pages", type=int, help="Max pages to crawl (for testing)", default=None)
    p.add_argument("--only-xml", action="store_true", help="Save only .xml documents")
    p.add_argument("--user-agent", help="User-Agent string (SEC requires contact info).", default="YourName/Email@example.com (Form4Crawler/1.0)")
    return p.parse_args()

def resolve_date_range(start_arg, end_arg, days_back):
    if start_arg and end_arg:
        start = datetime.strptime(start_arg, "%Y-%m-%d").date()
        end = datetime.strptime(end_arg, "%Y-%m-%d").date()
    elif start_arg and not end_arg:
        start = datetime.strptime(start_arg, "%Y-%m-%d").date()
        end = datetime.utcnow().date()
    else:
        end = datetime.utcnow().date()
        start = end - timedelta(days=days_back)
    start_ts = f"{start.isoformat()}T00:00:00Z"
    end_ts = f"{end.isoformat()}T23:59:59Z"
    return start_ts, end_ts

def build_query(start_ts, end_ts):
    return f'formType:"4" AND filedAt:[{start_ts} TO {end_ts}]'

def search_form4(session, query, page=1, page_size=100):
    params = {
        "q": query,
        "start": (page - 1) * page_size,
        "count": page_size,
        "sort": "filedAt desc",
    }
    url = f"{SEARCH_BASE}/?{urlencode(params)}"
    r = session.get(url)
    r.raise_for_status()
    return r.json()

def extract_accession_from_hit(hit):
    src = hit.get("_source", {})
    accession = src.get("accessionNumber") or src.get("accession")
    if not accession:
        accession = hit.get("id") or src.get("path")
    return accession, src

def filing_documents_url_from_source(src):
    filing_url = src.get("linkToFilingDetails")
    if filing_url:
        return filing_url
    cik = src.get("cik")
    accession = src.get("accessionNumber")
    if cik and accession:
        acc_no = accession.replace("-", "")
        return f"{EDGAR_BASE}/Archives/edgar/data/{int(cik)}/{acc_no}/{accession}-index.html"
    return None

def get_filing_documents(session, filing_detail_url):
    r = session.get(filing_detail_url)
    r.raise_for_status()
    tree = html.fromstring(r.content)
    doc_links = tree.xpath('//table[contains(@class,"tableFile")]//a[@href]')
    docs = []
    for a in doc_links:
        href = a.get("href")
        text = a.text_content().strip()
        if not href:
            continue
        full = urljoin(EDGAR_BASE, href)
        docs.append((text, full))
    return docs

def save_url_to_file(session, url, out_path):
    r = session.get(url, stream=True)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

def sanitize_filename(name):
    return re.sub(r'[^A-Za-z0-9._-]', '_', name)

def crawl_all_form4s(args):
    os.makedirs(args.output, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": args.user_agent, "Accept": "application/json"})
    start_ts, end_ts = resolve_date_range(args.start, args.end, args.days_back)
    query = build_query(start_ts, end_ts)
    # initial search to get totals
    data = search_form4(session, query, page=1, page_size=args.page_size)
    total_hits = data.get("hits", {}).get("total", 0)
    if isinstance(total_hits, dict):
        total_hits = total_hits.get("value", 0)
    total_pages = math.ceil(total_hits / args.page_size) if total_hits else 0
    if args.max_pages:
        total_pages = min(total_pages, args.max_pages)
    print(f"Query: {query}")
    print(f"Found ~{total_hits} Form 4 filings across {total_pages} pages.")
    for page in range(1, total_pages + 1):
        data = search_form4(session, query, page=page, page_size=args.page_size)
        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break
        for hit in hits:
            accession, src = extract_accession_from_hit(hit)
            filing_url = filing_documents_url_from_source(src)
            if not filing_url:
                continue
            folder_name = sanitize_filename(accession or filing_url.split("/")[-1])
            folder_path = os.path.join(args.output, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            try:
                docs = get_filing_documents(session, filing_url)
            except Exception as e:
                print(f"Failed to get filing docs for {filing_url}: {e}")
                time.sleep(args.delay)
                continue
            for doc_name, doc_url in docs:
                lower = doc_name.lower()
                url_lower = doc_url.lower()
                if args.only_xml:
                    if not url_lower.endswith(".xml") and ".xml" not in url_lower:
                        continue
                else:
                    # heuristics to pick primary docs
                    if not ("form4" in lower or ".xml" in url_lower or lower.endswith(".htm") or lower.endswith(".html") or lower.endswith(".txt") or "ownership" in lower):
                        continue
                fname = sanitize_filename(doc_name)
                out_path = os.path.join(folder_path, fname)
                if os.path.exists(out_path):
                    continue
                try:
                    save_url_to_file(session, doc_url, out_path)
                    print(f"Saved {doc_url} -> {out_path}")
                except Exception as e:
                    print(f"Failed to save {doc_url}: {e}")
                time.sleep(args.delay)
        time.sleep(args.delay)

def main():
    args = parse_args()
    crawl_all_form4s(args)

if __name__ == "__main__":
    main()
