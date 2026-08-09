import re
from typing import Optional, Dict, List, Tuple
import pandas as pd
import numpy as np


def _get_country_code(name: str) -> Optional[str]:
    """Map full country names or codes to ISO 2-letter uppercase codes."""
    mapping = {
        "czechia": "CZ", "cz": "CZ","tschechien":"CZ","tšekki":"CZ",
        "česká republika":"CZ","cesko":"CZ",
        "germany": "DE","deutschland":"DE", 
        "finland": "FI","suomi":"FI","finnland":"FI",
        "sweden": "SE","sverige":"SE" 
    }
    
    n = str(name).lower().strip() if name else ""
    for k,v in mapping.items():
        if n.startswith(k) or n == v: return v
    # If unknown, try to take first two chars? No. Return None implies unresolvable -> escalate logic handled elsewhere by caller. 
    return None


def _parse_month_name_to_num(name_part: str) -> Optional[int]:
    """Convert month name (e.g., 'Jan', 'Tammikuu') or number string to integer 1-6."""
    m = name_part.strip().lower() if isinstance(name_part, str) else ""
    
    months_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "tammikuu": 1, "helmikuu": 2, "maaliskuu": 3, 
        "huhtikuu": 4, "toukokuu": 5, "kesäkuu": 6
    }
    
    if m in months_map: return months_map[m]
    
    # Try parsing as number string like '1', '01' etc. (though usually names) 
    try:
        num = int(m.replace(' ', '').replace('/', ''))
        if 1 <= num <= 6: return num
    except ValueError: pass
    
    return None


def _extract_sales_clean(val):
    """Clean and convert sales value to float, handling European comma separator."""
    v = str(val).strip().replace('"', '').replace(' ', '')
    
    # Handle empty or NaN-like strings
    if not v: return np.nan
    
    try:
        # If contains comma (European format) -> replace with dot. 
        if ',' in v:
            parts = v.split(',')
            if len(parts) == 2: 
                return float(v.replace(',','.'))
        
        else:
            # No comma -> standard dot separator? Or maybe integer? Try direct conversion first.
            try: return float(v)
            except ValueError: pass
        
    except (ValueError, OverflowError):
        return np.nan
    
    return np.nan


def _parse_period_from_value(val_str: str) -> Optional[str]:
    """Parse a string value to YYYY-MM format if it contains month/year info."""
    
    clean_val = re.sub(r'["\s]', '', val_str).strip() # Remove quotes and spaces for parsing
    
    # Pattern 1: Explicit YYYY-MM (e.g., "2026-01")
    m_dash_match = re.match(r'^(\d{4})-(\d{2})$', clean_val)
    if m_dash_match: 
        return f"{m_dash_match.group(1)}-{int(m_dash_match.group(2)):02}"

    # Pattern 2: M/YYYY (e.g., "3/2026") -> Convert to YYYY-MM.
    slash_match = re.match(r'^(\d{1,2})/(20\d{3})$', clean_val)
    if slash_match:
        month_str = slash_match.group(1) # e.g., '3' or 'Jan'? Regex matched numbers only here due to 20\d pattern. 
        year_int = int(slash_match.group(2))
        
        return f"{year_int}-{int(month_str):02}"

    # Pattern 3: Combined Month Name and Year (e.g., "Tammikuu 2026", "Januar 2026") 
    month_year_match = re.match(r'^([A-Za-z]+|\d+) \s*(\d{4})$', clean_val)
    
    if not slash_match: # Only check this if no simple number-year split found? Actually, D10 has "Januar 2026". 
        try:
            mon_part_str = month_year_match.group(1).strip()
            year_int = int(month_year_match.group(2))
            
            # Try to convert mon_part_str (name or number) to numeric month.
            num_month = _parse_month_name_to_num(mon_part_str) if isinstance(mon_part_str, str) else None
            
            if num_month is not None:
                return f"{year_int}-{num_month:02}"
        except Exception: pass
    
    # Pattern 4: Wide format columns (like 'JAN', 'FEB') are handled by column iteration logic outside this helper. 
    # This function only handles values inside a single cell that contain date info.

    return None


def normalize(source_path: str) -> pd.DataFrame:
    
    df = pd.read_csv(source_path, dtype=str).fillna('')  # Fill NA with empty string to simplify .get() calls
    
    country_col_name = None
    product_col_name = None
    
    cols_lower = [c.lower() for c in df.columns]
    
    # Identify Country Column
    if "country" in cols_lower:
        idx_c = cols_lower.index("country")
        country_col_name = list(df.columns)[idx_c]
        
    elif any(x in str(c) for x in ["maa","land"]): 
        # Pick first column containing these keywords.
        for c in df.columns:
            if "maa" in str(c).lower() or "land" in str(c).lower():
                country_col_name = c
                break
    
    else: return pd.DataFrame(columns=["country","product_id","period","sales"]) # Should not happen per task spec.

    
    product_keywords = ["product","tuote","produkt"] 
    for c in df.columns:
        if any(kw in str(c).lower() for kw in product_keywords):
            product_col_name = c
            break
            
    rem_cols_list = [c for c in df.columns if c != country_col_name and c != product_col_name]

    
    results_rows = []
    
    # Map month names to numbers globally used in wide formats. 
    months_map_reverse: Dict[str, int] = {
        "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
        "tammikuu":1,"helmikuu":2,"maaliskuu":3,"huhtikuu":4,"toukokuu":5,"kesäkuu":6
    }

    
    for idx in range(len(df)): 
        row = df.iloc[idx] 
        
        c_val_str = str(row[country_col_name]) if country_col_name else ""
        
        # If no country column found (should not happen), skip or handle? Assume it exists.
        if not c_val_str: continue
        
        p_val_str = str(row.get(product_col_name)) if product_col_name and product_col_name in df.columns else ""

        country_code = _get_country_code(c_val_str)
        
        # If we couldn't identify a valid country code from the string, treat as unresolvable? 
        # For now assume mapping covers all cases. 
        if not country_code: continue
        
        product_id = p_val_str.strip()

        found_period = False
        sales_cleaned_value = np.nan
        
        for c in rem_cols_list:
            v_str = str(row[c])
            
            period_val = _parse_period_from_value(v_str)
            
            if period_val is not None and period_val != "": 
                # Found a valid date string. Now get the sales value from this row/cell? 
                # Wait, in wide format (D02), 'period' isn't explicit column but multiple month columns exist. 
                # In D07/D14 style with combined Period column, we need to find which one is period and where sales is.
                # My logic above assumes if a value matches YYYY-MM or M/YYYY pattern, it's the date AND its partner cell holds sales? No!
                
                # Correction: 
                # Case A (D01/D03): One 'period' column contains "2026-01", another 'sales' column. But D07 has Period and Sales in same row but different columns? Yes, separate cols.
                # Case B (Wide format like D05): Columns are JAN,FEB... The period is implicit from col name or value inside sales cell? No! 
                # In wide formats, the 'sales' column usually contains numbers for specific months and empty/NaN for others. We need to infer which month it corresponds to based on COLUMN NAME (JAN vs FEB).
                
                pass 

        if not found_period: continue
        
    return pd.DataFrame(columns=["country","product_id","period","sales"])
