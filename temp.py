import json
import pandas as pd
from datetime import timedelta
import os

def analyze_insider_clusters(input_filename, window_days=14, min_insiders=2):
    """
    Groups insider trades into 14-day windows and flags clusters where multiple 
    high-level directors/officers traded close together.
    """
    if not os.path.exists(input_filename):
        print(f"Error: {input_filename} not found.")
        return

    with open(input_filename, 'r') as f:
        data = json.load(f)

    # 1. Filter for High-Level Officers/Directors only
    target_roles = ['director', 'president', 'ceo', 'coo', 'cfo', 'vp', 'chairman', 'chief', 'general counsel']
    
    rows = []
    for entry in data:
        role = str(entry.get('role', '')).lower()
        # Filter for Board members OR people with target keywords in their title
        if entry.get('is_on_board', False) or any(r in role for r in target_roles):
            for tx in entry.get('transactions', []):
                rows.append({
                    'ticker': entry['ticker'],
                    'company': entry['company_name'],
                    'insider': entry['insider_name'],
                    'role': entry.get('role', 'N/A'),
                    'date': pd.to_datetime(tx['date']),
                    'action': tx['action'],
                    'shares': tx['shares'],
                    'value': tx.get('total_value', 0)
                })

    df = pd.DataFrame(rows)
    if df.empty:
        print("No high-level trades found.")
        return

    results = []
    
    # 2. Analyze by Company
    for company, group in df.groupby('company'):
        group = group.sort_values('date')
        
        # Track which dates we've already "covered" in a cluster to avoid redundant output
        covered_until = pd.Timestamp.min

        for i, start_trade in group.iterrows():
            if start_trade['date'] <= covered_until:
                continue
                
            window_end = start_trade['date'] + timedelta(days=window_days)
            window_trades = group.loc[(group['date'] >= start_trade['date']) & (group['date'] <= window_end)]
            
            unique_insiders = window_trades['insider'].unique()
            
            # 3. Only keep if at least X different high-level people traded in this window
            if len(unique_insiders) >= min_insiders:
                # Calculate the cluster sentiment (more buyers = bullish, more sellers = bearish)
                buy_count = (window_trades['action'] == 'BUY').sum()
                sell_count = (window_trades['action'] == 'SELL').sum()
                
                cluster_info = {
                    "company": company,
                    "ticker": window_trades['ticker'].iloc[0],
                    "cluster_start": str(start_trade['date'].date()),
                    "cluster_end": str(window_trades['date'].max().date()),
                    "insider_count": int(len(unique_insiders)),
                    "total_net_value": float(window_trades.apply(lambda x: x['value'] if x['action'] == 'BUY' else -x['value'], axis=1).sum()),
                    "sentiment": "BULLISH" if buy_count > sell_count else "BEARISH",
                    "insiders_involved": []
                }

                # Build summary list of insiders in this specific cluster
                for name in unique_insiders:
                    p_trades = window_trades[window_trades['insider'] == name]
                    cluster_info["insiders_involved"].append({
                        "name": name,
                        "role": p_trades['role'].iloc[0],
                        "summary": f"{p_trades['action'].iloc[0]} {int(p_trades['shares'].sum()):,} total shares"
                    })
                
                results.append(cluster_info)
                # Move forward so we don't report the same cluster overlappingly
                covered_until = window_end

    # 4. Save to JSON
    output_filename = f"cluster_analysis.json"
    with open(output_filename, 'w') as f:
        json.dump(results, f, indent=4)
    
    print(f"Success. Found {len(results)} clusters. Results saved to {output_filename}")

if __name__ == "__main__":
    analyze_insider_clusters('insider_analysis.json')