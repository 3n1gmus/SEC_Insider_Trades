# pip install pandas

import json
import pandas as pd
from collections import defaultdict
import os

def analyze_insider_clusters(input_filename, share_threshold=10000):
    """
    Analyzes insider trading data for clusters of high-level activity.
    
    :param input_filename: The name of the JSON file to review.
    :param share_threshold: Minimum total shares per company to be included in the report.
    """
    if not os.path.exists(input_filename):
        print(f"Error: The file '{input_filename}' was not found.")
        return

    with open(input_filename, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"Error: Failed to decode JSON from '{input_filename}'.")
            return

    # Dictionary to aggregate activity by company
    company_activity = defaultdict(lambda: {
        "insiders": set(),
        "total_shares_bought": 0,
        "total_shares_sold": 0,
        "total_value_bought": 0.0,
        "total_value_sold": 0.0,
        "insider_details": []
    })

    # Filter keywords for high-level roles
    target_roles = ['Director', 'President', 'CEO', 'COO', 'CFO', 'VP', 'General Counsel', 'Chief']

    for entry in data:
        company = entry['company_name']
        insider = entry['insider_name']
        role = entry.get('role', 'N/A')
        is_board = entry.get('is_on_board', False)
        
        # Check if insider is a Director or a C-Suite Officer
        is_high_level = is_board or any(r.lower() in str(role).lower() for r in target_roles)

        if is_high_level:
            for tx in entry['transactions']:
                shares = tx['shares']
                price = tx.get('price_per_share', 0.0)
                
                # Use total_value if present, otherwise calculate it
                value = tx.get('total_value', 0.0)
                if value == 0 and price > 0:
                    value = shares * price
                
                if tx['action'] == 'BUY':
                    company_activity[company]["total_shares_bought"] += shares
                    company_activity[company]["total_value_bought"] += value
                else:
                    company_activity[company]["total_shares_sold"] += shares
                    company_activity[company]["total_value_sold"] += value
            
            # Record unique high-level individuals
            if insider not in company_activity[company]["insiders"]:
                company_activity[company]["insiders"].add(insider)
                company_activity[company]["insider_details"].append(f"{insider} ({role})")

    # Generate results for companies with more than one unique high-level insider
    results = []
    for company, info in company_activity.items():
        total_volume = info["total_shares_bought"] + info["total_shares_sold"]
        
        if len(info["insiders"]) > 1 and total_volume >= share_threshold:
            net_shares = info["total_shares_bought"] - info["total_shares_sold"]
            net_value = info["total_value_bought"] - info["total_value_sold"]
            results.append({
                "Company": company,
                "Insiders Count": len(info["insiders"]),
                "Net Shares": net_shares,
                "Net Value ($)": net_value,
                "Insiders Involved": "; ".join(info["insider_details"])
            })

    # Output results
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by="Insiders Count", ascending=False)
        output_file = f"analysis_of_{input_filename.split('.')[0]}.csv"
        df.to_csv(output_file, index=False)
        print(f"Analysis complete. Results saved to {output_file}")
        print(df)
    else:
        print(f"No high-level insider clusters meeting the threshold were found in '{input_filename}'.")

# --- CONFIGURATION ---
# Set the name of the file you want to review here:
FILE_TO_REVIEW = 'insider_analysis.json'

if __name__ == "__main__":
    analyze_insider_clusters(FILE_TO_REVIEW)