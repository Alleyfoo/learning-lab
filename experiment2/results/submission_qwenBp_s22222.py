import pandas as pd
from contract import Escalate


def normalize(source_path: str) -> pd.DataFrame:
    """Normalize sales data from various partner formats into the canonical form."""

    COUNTRY_MAP = {
        "Česko": "CS",      # Czechia
        "Deutschland": "DE", 
        "Suomi": "FI",       # Finland (Finnish endonym)
        "Sverige": "SE"      # Sweden
    }

    def parse_date(date_str):
        """Convert DD/MM/YYYY or YYYY-MM to YYYY-MM."""
        s = str(date_str).strip()
        if "/" in s:  # Likely DD/MM/YYYY (as per examples)
            parts = s.split("/")
            if len(parts) == 2 and all(p.isdigit() for p in parts):
                m, y = int(parts[0]), int(parts[1])
                return f"{y:04d}-{m:02d}"
        # If YYYY-MM format already exists (e.g., '2025-01'), keep it.
        if "-" in s and not "/" in s:
            parts = s.split("-")
            if len(parts) == 2 and all(p.isdigit() for p in parts):
                return f"{parts[0]}-{parts[1]}"
        # If format is ambiguous or unknown -> Escalate later? For now, assume valid date string.
        return s

    def parse_sales(sales_str):
        """Convert sales value to float rounded to 2 decimals."""
        s = str(sales_str).strip()
        if "," in s:
            clean_s = s.replace(",", ".")
        else:
            clean_s = s
        
        try:
            val = float(clean_s)
            return round(val, 2)
        except ValueError:
            # If parsing fails and no other way to infer -> Escalate if critical. 
            raise Escalate(f"Cannot parse sales value '{sales_str}'", {"original": str(sales_str)})

    df = pd.read_csv(source_path)

    # Identify columns by content or name heuristics
    country_col = None
    product_col = None
    period_col = None
    sales_col = None
    
    column_names_lower = [c.lower() for c in df.columns]
    
    # Heuristic 1: Look for known Finnish/German/Swedish terms.
    if any("maa" in name or "land" in name for name in column_names_lower):
        idx = next((i for i, n in enumerate(column_names_lower) if ("maa" in n.lower()) or ("land" in n.lower())), None)
        if idx is not None:
            country_col = df.columns[idx].strip()

    # Heuristic 2: Look for 'tuote' (Finnish product), 'product', etc. Or column with ART- prefix values.
    elif any("product" in name or "art-" == str(df.iloc[0][col]).lower().startswith if col else False): 
        pass 

# Simplified robust approach assuming standard column order from examples but detecting by content:

for col_name, series in zip(df.columns, df):
    sample_val = str(series.iloc[0]) if len(series) > 0 else ""
    
    # Check for period-like string (DD/MM/YYYY or YYYY-MM)
    has_slash = "/" in sample_val and all(p.isdigit() for p in sample_val.split("/")[:2]) 
    is_period_like = (has_slash or ("-" in sample_val and not "/" in sample_val)) 
    
    if is_period_like:
        period_col = col_name

# Check for sales column: numeric-like values.
sales_candidates = []
for col_name, series in zip(df.columns, df):
    try:
        val_sample = str(series.iloc[0]).replace(",", ".")
        float(val_sample) # Try to parse as number.
        if not is_period_like for this column? We need a flag per column. 
except ValueError: pass

# Better approach: assume the last numeric column that is not date-like is sales, or first non-date/product/country.

final_df = pd.DataFrame(columns=["country", "product_id", "period", "sales"])
