import json
import pandas as pd
from collections import defaultdict
import os

def analyze_insider_clusters(input_filename, share_threshold=10000):
    if not os.path.exists(input_filename):
        print(f"Error: The file '{input_filename}' was not found.")
        return

    with open(input_filename, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"Error: Failed to decode JSON from '{input_filename}'.")
            return

    # Dictionary now also stores the ticker for each company
    company_activity = defaultdict(lambda: {
        "ticker": "N/A", # Placeholder for the ticker
        "insiders": set(),
        "total_shares_bought": 0,
        "total_shares_sold": 0,
        "total_value_bought": 0.0,
        "total_value_sold": 0.0,
        "insider_details": []
    })

    target_roles = ['Director', 'President', 'CEO', 'COO', 'CFO', 'VP', 'General Counsel', 'Chief']

    for entry in data:
        company = entry['company_name']
        ticker = entry.get('ticker', 'N/A') # Extract ticker
        insider = entry['insider_name']
        role = entry.get('role', 'N/A')
        is_board = entry.get('is_on_board', False)
        
        is_high_level = is_board or any(r.lower() in str(role).lower() for r in target_roles)

        if is_high_level:
            # Save the ticker for the company entry
            company_activity[company]["ticker"] = ticker
            
            for tx in entry['transactions']:
                shares = tx['shares']
                price = tx.get('price_per_share', 0.0)
                value = tx.get('total_value', 0.0)
                if value == 0 and price > 0:
                    value = shares * price
                
                if tx['action'].upper() == 'BUY':
                    company_activity[company]["total_shares_bought"] += shares
                    company_activity[company]["total_value_bought"] += value
                else:
                    company_activity[company]["total_shares_sold"] += shares
                    company_activity[company]["total_value_sold"] += value
            
            if insider not in company_activity[company]["insiders"]:
                company_activity[company]["insiders"].add(insider)
                company_activity[company]["insider_details"].append(f"{insider} ({role})")

    results = []
    for company, info in company_activity.items():
        total_volume = info["total_shares_bought"] + info["total_shares_sold"]
        
        if len(info["insiders"]) > 1 and total_volume >= share_threshold:
            net_shares = info["total_shares_bought"] - info["total_shares_sold"]
            net_value = info["total_value_bought"] - info["total_value_sold"]
            
            operation_type = "BUY" if net_value > 0 else "SELL" if net_value < 0 else "NEUTRAL"

            results.append({
                "Ticker": info["ticker"], # New Column Added
                "Company": company,
                "Operation": operation_type,
                "Insiders Count": len(info["insiders"]),
                "Net Shares": net_shares,
                "Net Value ($)": round(net_value, 2),
                "Insiders Involved": "; ".join(info["insider_details"])
            })

    df = pd.DataFrame(results)
    if not df.empty:
        # Sort by count and then value
        df = df.sort_values(by=["Insiders Count", "Net Value ($)"], ascending=[False, False])
        output_file = f"analysis_of_{os.path.splitext(input_filename)[0]}.csv"
        df.to_csv(output_file, index=False)
        print(f"Analysis complete. Results saved to {output_file}")
    else:
        print(f"No clusters meeting the criteria were found.")

FILE_TO_REVIEW = 'insider_analysis.json'

if __name__ == "__main__":
    analyze_insider_clusters(FILE_TO_REVIEW)