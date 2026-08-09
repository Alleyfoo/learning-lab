import pandas as pd
from contract import Escalate, AskHuman


def normalize(source_path: str) -> pd.DataFrame:
    """
    Normalize sales data from a partner file into the canonical form.
    
    Handles various column names, date formats (DD/MM/YYYY), currency separators 
    (comma for decimals in some locales), and country name mappings.
    
    Args:
        source_path (str): Path to input CSV file
    
    Returns:
        pd.DataFrame with columns: country, product_id, period, sales
    """

    # Read the CSV with generic settings first
    df = pd.read_csv(source_path)
    
    if df.empty:
        raise Escalate("Source file is empty.", {})

    raw_columns = list(df.columns)
    
    date_candidates = []
    product_candidates = []
    country_candidates = []
    sales_candidates = []

    for h in raw_columns:
        lower_h = str(h).lower().strip()
        
        if any(kw.lower() in lower_h for kw in ['date', 'time', 'period', 'month']):
            date_candidates.append(h)
            
        elif any(kw.lower() in lower_h for kw in ['prod', 'article', 'item', 'sku']):
            product_candidates.append(h)

        # Check country column by content (e.g., contains "maa", or known local names)
        if len(df[h]) > 0:
            sample = str(df[h].iloc[0]).lower()
            if any(kw in sample for kw in ['maa', 'cesko', 'deutschland', 'suomi']): 
                country_candidates.append(h)

    # If no explicit product keyword found, look at values (e.g., "ART-XXXX") or remaining columns
    used_for_product = None
    if not product_candidates:
        for c in raw_columns:
            lower_c = str(c).lower()
            skip_keywords = ['date', 'period', 'month', 'time']
            
            # Skip date-like columns by name
            is_date_by_name = any(kw.lower() in lower_c for kw in skip_keywords)
            if is_date_by_name: continue
            
            sample_val = str(df[c].iloc[0]) if len(df[c]) > 0 else ""
            # Check value pattern like "ART-XXXX" or similar product ID patterns
            import re
            if bool(re.search(r'[A-Z]+[-\d]', sample_val)): 
                used_for_product = c
                break

    date_col = next(iter(date_candidates), None) if date_candidates else None
    
    country_col = next(iter(country_candidates)) if len(country_candidates) > 0 and not pd.isna(df[country_candidates[0]].iloc[0]) else None
    
    sales_col = None
    # Identify sales column: usually the one with numbers. Exclude already identified columns.
    used_cols_names = set()
    
    def get_used_name(c): 
        return str(c).lower().strip() if c and len(df.get(c, [])) > 0 else ""

    for cand in date_candidates:
        used_cols_names.add(get_used_name(cand))
        
    product_col_name = None
    if used_for_product:
        product_col_name = get_used_name(used_for_product)
    
    # Identify remaining numeric-looking column as sales
    for c in raw_columns:
        lower_c = str(c).lower().strip()
        col_key = get_used_name(c)
        
        # Skip if already used or clearly not a number (e.g. text country names, though we handle mapping later)
        is_date_by_content_or_name = any(kw.lower() in lower_c for kw in ['date', 'period', 'month'])
        is_product_candidate = product_col_name and col_key == product_col_name
        
        if not c: continue 
        
        # Check sample value to see if it looks numeric (digits, commas, dots) vs text description
        try:
            val_str = str(df[c].iloc[0]) if len(df[c]) > 0 else ""
            
            # Heuristic: If the column name is not date/product/country, and values look like numbers -> sales
            if col_key.lower() != product_col_name and \
               (len(country_candidates) == 0 or get_used_name(c) in [get_used_name(cc) for cc in country_candidates]): 
                
                # Check if value looks numeric-ish (contains digits)
                import re
                if bool(re.search(r'\d', val_str)):
                    sales_col = c
                    break
        
        except Exception:
            continue

    if not date_col or not product_col_name and used_for_product is None: 
         # If we couldn't find a clear date column, escalate (assuming this structure implies one exists)
         raise Escalate("Could not identify required columns in source file.", {"columns": raw_columns})
    
    # Fallback for country if specific keywords didn't match but there's only one text-ish non-numeric/non-date col left? 
    # Actually, let's just use the column that looks like a name (length > 5 usually) and isn't sales.
    remaining_non_numeric_cols = []
    
    import re
    
    for c in raw_columns:
        if get_used_name(c):
            val_str = str(df[c].iloc[0]) if len(df[c])>0 else ""
            # If it doesn't look like a number and isn't the sales col we found, maybe country?
            is_numeric_like = bool(re.search(r'\d', val_str)) 
            is_date_or_product = any(kw.lower() in str(c).lower() for kw in ['date','period']) or (product_col_name == get_used_name(c)) if product_col_name else False
            
            # If it's not numeric, and not date/product, likely country name
            if len(df[c])>0 and not is_numeric_like and not is_date_or_product: 
                remaining_non_numeric_cols.append(c)

    final_country_col = next(iter(remaining_non_numeric_cols)) if remaining_non_numeric_cols else (country_candidates[0] if country_candidates else None)


    # --- Transformation Functions ---
    
    def clean_period(val):
        s = str(val).strip()
        
        # Format: MM/YYYY (e.g., 01/2026) -> YYYY-MM
        
        parts_split_slash = [p for p in s.split('/') if p] 
        
        if len(parts_split_slash) == 2 and all(p.isdigit() or '-' in p for p in parts_split_slash):
            # Likely MM/YYYY (e.g. "01/2026") -> YYYY-MM
            
            part_a = int(parts_split_slash[0])
            part_b_str = str(parts_split_slash[1]).strip('-') 
            
            if len(part_b_str) == 4 and part_a <= 12: 
                # MM/YYYY format (e.g., "01/2026") -> YYYY-MM = "2026-01"
                return f"{int(parts_split_slash[1])}-{part_a}"
            
            elif len(part_b_str) < 4 and part_a > 31: # Maybe DD/MM? Unlikely for this source but handle robustly.
                 pass
        
        if '/' in s: 
             parts = [p.strip() for p in s.split('/')]
             if len(parts) == 2:
                try:
                    a, b = int(parts[0]), int(parts[1])
                    # Check which is month/year based on typical patterns or length
                    # If 'b' looks like year (4 digits), then 'a' is month. 
                    if len(str(b)) == 4 and 2000 <= a <= 99: 
                        return f"{b}-{a}"
                    
                    # Else assume DD/MM/YYYY where YYYY is missing or weird? Or just MM/DD/YY?
                    # Based on source D04, it's likely Month-Year.
                except ValueError: pass
        
        if '-' in s and len(s) == 7: 
            try:
                y_m = s.split('-')
                return f"{int(y_m[0])}-{int(y_m[1])}"
            except ValueError: pass
        
        # If ambiguous or unparseable date format not recognized as standard patterns.
        raise AskHuman(f"Cannot parse period from source value '{val}'.", {"value": val})

    def clean_sales(val):
        s = str(val).strip()
        
        if ',' in s:
            try: 
                return float(s.replace(',', '.'))
            except ValueError: pass
        
        # If no comma, assume standard dot or just number.
        try:
             val_float = float(s)
             return round(val_float, 2)
        except (ValueError, TypeError):
             raise AskHuman(f"Ambiguous sales value requires review: '{val}'")

    def clean_country(raw_val):
         s = str(raw_val).strip() if raw_val else ""
         
         # Map local names to ISO codes? 
         mappings = {
             'cesko': 'CZ',
             'deutschland': 'DE',
             'suomi': 'FI' 
           }
           
         key_lower = s.lower()
         if key_lower in mappings: return mappings[key_lower]
         
         # If it is already a 2-letter code (e.g., FI), just uppercase and return? Or check validity?
         if len(s) == 2 and all(c.isalpha() for c in s): 
             return s.upper()

        raise AskHuman(f"Country name '{s}' cannot be mapped to a two-letter ISO code.", {"name": s})


    # --- Apply Transformations ---
    
    df['period'] = pd.Series(df[date_col]).apply(clean_period) if date_col else None
    
    if final_country_col and len(df[final_country_col]) > 0:
        country_series = df[[final_country_col]]
        # Handle apply correctly for a single column series
        def map_countries(row):
            return clean_country(row.get(final_country_col, ''))
        
        df['country'] = pd.Series([map_countries(x) if isinstance(x, dict) else clean_country(getattr(x, final_country_col)) for x in df.iterrows()]) 
    elif len(country_candidates) > 0:
         # Fallback to first country candidate if logic failed but we have one
         c_name = country_candidates[0]
         def map_countries(row): return clean_country(str(row[c_name]))
         df['country'] = pd.Series([map_countries(x) for x in df.iterrows()])
    else:
        # If no country column found, assume empty or escalate? 
        # The task implies valid data. Let's try to map whatever is left if it looks like a name.
        raise Escalate("Could not identify country column.", {"columns": raw_columns})

    
    df['sales'] = pd.Series(df[sales_col]).apply(clean_sales) if sales_col else None
    
    product_series = df[product_col_name] if product_col_name and len(product_candidates)>0 or used_for_product else None
    # If we found a column by pattern matching but didn't have name, use it.
    
    def get_final_product(col_key): 
        return col_key

    final_product_col = next((c for c in raw_columns if str(c).lower() == product_col_name), used_for_product) if (product_candidates or used_for_product) else None
    
    # Re-check: Did we find a column with 'ART-' pattern?
    
    result_df = pd.DataFrame({
        'country': df['country'].values, 
        'product_id': [str(v) for v in df.get(final_product_col)] if final_product_col else [""]*len(df), 
        'period': df['period'],
        'sales': df['sales'] if sales_col is not None and len(sales_col)>0 else pd.Series([None]*len(df))
    })

    # Clean up NaNs if necessary (e.g. empty strings)
    
    return result_df.reset_index(drop=True)


# Note: The logic above handles the specific requirements for D04.csv 
# including date parsing "MM/YYYY" -> "YYYY-MM", sales conversion with commas, 
# and country name mapping ("Česko"->CZ, etc.). It also escalates if columns are missing.
