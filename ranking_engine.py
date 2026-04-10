import pandas as pd
import numpy as np

class MutualFundRanker:
    def __init__(self, file_path):
        try:
            self.df = pd.read_csv(file_path)
        except Exception:
            self.df = pd.read_excel(file_path)
        self.clean_data()

    def clean_data(self):
        mapping = {
            'AUM': ['AUM', 'Assets', 'Fund Size'],
            'Age': ['Age', 'Years', 'Inception'],
            'Standard Deviation': ['Standard Deviation', 'Std Dev', 'Volatility'],
            'Sharpe': ['Sharpe', 'Sharpe Ratio'],
            'Sortino': ['Sortino', 'Sortino Ratio'],
            'Fund Name': ['Fund Name', 'Scheme Name'],
            'Scheme Category': ['Scheme Category', 'Category'],
            'Fund Type': ['Fund Type', 'Type']
        }
        new_columns = {}
        for target, aliases in mapping.items():
            for col in self.df.columns:
                if col.strip() in aliases:
                    new_columns[col] = target
        self.df.rename(columns=new_columns, inplace=True)

        critical_cols = ['Sharpe', 'Sortino', 'Standard Deviation', 'AUM', 'Age']
        for col in critical_cols:
            if col not in self.df.columns:
                self.df[col] = 0
            self.df[col] = pd.to_numeric(self.df[col].astype(str).str.replace('%', ''), errors='coerce').fillna(0)

    def calculate_ranks(self, scheme_name, risk_profile="Balanced", fund_type=None):
        # FIX: You must define search_term BEFORE using it
        search_term = str(scheme_name).strip().lower() 
        
        # Create the helper column for matching
        self.df['match_col'] = self.df['Scheme Category'].astype(str).str.strip().str.lower()
        
        # Now use search_term to filter
        filtered = self.df[self.df['match_col'].str.contains(search_term, na=False)].copy()
        
        if filtered.empty:
            return filtered
        
        # ... (rest of your ranking logic)

        # 3. Percentile Rankings (Same logic as before)
        for col in ['AUM', 'Age', 'Sharpe', 'Sortino']:
            filtered[f'{col}_p'] = filtered[col].rank(pct=True)
        
        filtered['Rev_StdDev_p'] = 1 - filtered['Standard Deviation'].rank(pct=True)

        # 4. Stability Score
        filtered['Stability Score'] = (0.60 * filtered['AUM_p']) + (0.40 * filtered['Age_p'])

        # 5. Risk Quality Score
        if risk_profile == "Safer":
            filtered['Risk Quality Score'] = (0.3*filtered['Sharpe_p']) + (0.3*filtered['Sortino_p']) + (0.4*filtered['Rev_StdDev_p'])
        elif risk_profile == "Aggressive":
            filtered['Risk Quality Score'] = (0.45*filtered['Sharpe_p']) + (0.45*filtered['Sortino_p']) + (0.1*filtered['Rev_StdDev_p'])
        else:
            filtered['Risk Quality Score'] = (0.4*filtered['Sharpe_p']) + (0.4*filtered['Sortino_p']) + (0.2*filtered['Rev_StdDev_p'])

        filtered['Final Score'] = (0.50 * filtered['Stability Score']) + (0.50 * filtered['Risk Quality Score'])
        
        return filtered.sort_values(by='Final Score', ascending=False)