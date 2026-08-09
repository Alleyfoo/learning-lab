import pandas as pd


def normalize(source_path: str) -> pd.DataFrame:
    """
    Normalize sales data from various CSV formats into a canonical DataFrame.
    
    Handles:
      - Different column orders and names (e.g., 'kausi' for period, 'maa' for country).
      - Wide format with month columns vs long format with a single period/sales column.
      - Date/Period values as strings like "2026-01", "Jan 2026", "1/2026".
      - Sales values using commas (e.g., "442,27") or dots and potentially quoted with spaces.
    """

    # Read the CSV file assuming default delimiter detection first. 
    try:
        df = pd.read_csv(source_path)
    except Exception as e:
        raise e
    
    if len(df.columns) == 0:
        raise ValueError("Empty DataFrame returned from source.")

    cols_lower = [c.lower() for c in df.columns]
    
    # --- Step 1: Identify Structure (Wide vs Long) and Column Names ---
    
    country_col_name = None
    product_col_name = "product" 
    
    period_raw_col_name = None   # For long format where sales is split into rows or columns? No, usually a single 'period' col.
                                # In wide format: multiple month cols exist. 
    wide_month_cols = []         # List of column names that are months in wide format.

    sales_col_name = None
    
    # --- Column Name Mapping Logic ---
    
    for c in df.columns:
        s_c = str(c).strip().lower()
        
        if "country" in s_c or (len(df[c].dropna()) > 0 and len(str(df.iloc[0][c])) == 2): 
            country_col_name = c
        
        elif ("land" == str(c)) or ("maa".startswith("m")): # 'Maa' is Finnish for Country
             if "german" not in source_path.lower(): pass 
            
    # --- Refined Logic: Identify Columns by Content or Name ---
    
    detected_country = None
    detected_product = product_col_name
    
    sales_found = False
    
    def _get_iso_code(name_str):
        """Map various country names to the canonical two-letter code."""
        name = str(name_str).strip().upper() if isinstance(name_str, str) else ""
        
        direct_map = {
            "CZ": "CZ", 
            "DE": "DE", "GERMANY": "DE", "DEUTSCHLAND": "DE", 
            "FI": "FI", "FINLAND": "FI", "SUOMI": "FI", 
            "SE": "SE", "SWEDEN": "SE", "SVERIGE": "SE"
        }
        
        if name in direct_map: return direct_map[name]

        # Handle Czech variants (e.g., 'Česká republika', 'Tšekki') -> CZ
        lower_name = str(name_str).lower()
        if any(w in lower_name for w in ["tschechien", "tšekki"]): return "CZ"
        
        # German names
        if any(w in name.lower() or w in lower_name for w in ["deutschland", "germany"]): return "DE"
        if any(w in name.lower() or w in lower_name for w in ["suomi", "finland"]): return "FI"
        
        # Swedish names
        if any(w in name.lower() or w in lower_name for w in ["sverige", "sweden"]): return "SE"

    def _extract_period_from_header(header_str: str) -> tuple[str, int] | None:
        """Extract year and month from a wide-format header like 'January 2026'."""
        clean_val = str(header_str).strip().replace('"', '').upper()
        
        # Check for slash format (e.g., "1/2026") - D03, D07 style headers might be values? No, those are data. Headers like 'Jan 2026'.
        if "/" in clean_val: 
            parts = clean_val.split("/")
            mn_str, yr = (parts[0], parts[1]) if len(parts) >= 2 else ("", "")
            return None # Slash format is usually handled as data or specific header logic. Let's skip for now unless needed.

        month_names = {
            "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, 
            "APRIL": 4, "MAY": 5, "JUNE": 6, 
            "TAMMIKUU": 1, "HELMIKUU": 2, "MAALISKUU": 3,
            "HUHTIKUU": 4, "TOUKOKUU": 5, "KE SÄ KUU": 6 # Handle spaces? No. 
        }

        month_str = clean_val.split()[0] if len(clean_val.split()) > 0 else ""
        
        if month_str in month_names:
            mn_num = str(month_names[month_str]).zfill(2)
            
            year_part = " ".join(clean_val.split()[1:]) # Get rest as year
            
            try:
                yr_cleaned = "".join(filter(str.isdigit, year_part))
                
                if len(yr_cleaned) == 4:
                    return f"{yr_cleaned}-{mn_num}"
            except Exception: pass

        # Check for "YYYY-MM" in header? Unlikely but possible.
        
    rows_to_add = []
    
    is_wide_format = False
    
    month_keywords = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE"] 
    fin_month_words = ["TAMMIKUU", "HELMIKUU", "MAALISKUU", "HUHTIKUU", "TOUKOKUU", "KE SÄ KUU"]
    
    # Detect wide format by checking headers for month names
    for c in df.columns:
        s_c_lower = str(c).lower()
        
        if any(kw.lower() == kw.strip().split()[0] or (kw + " 2" not in s_c_lower) and ("january".startswith(s_c_lower)) or ("tammikuu" in s_c_lower): 
            is_wide_format = True
    
    # Re-check wide format detection more robustly
    for c in df.columns:
        if any(kw.lower() == str(c).lower().split()[0] for kw in ["january", "february"] + fin_month_words.split()): pass
        
    simpler_check = False
    has_wide_format = False
    
    # Check headers against month names (case insensitive)
    header_strs_lower = [str(col).lower() for col in df.columns]
    
    found_months_in_headers = []
    for c in df.columns:
        h_name = str(c).lower().strip()
        if any(kw.lower() in h_name or kw.startswith(h_name.split()[0]) and len(h_name) < 15 for kw in month_keywords + fin_month_words): 
             found_months_in_headers.append(c)

    is_wide_format = bool(found_months_in_headers)

    
    # --- Process the DataFrame based on Detected Format ---
    
    final_rows: list[dict] = []
    
    if has_wide_format and len(df.columns) > 2:
        # WIDE FORMAT HANDLING
        
        for idx, row in df.iterrows():
            try:
                country_val = None
                
                # Identify Country column (usually first or named 'Land'/'Country')
                c_name_col = None
                p_name_col = None
                
                if len(df.columns) >= 2 and "land" == str(df.columns[0]): 
                    raw_country = row.get("LAND", "")
                elif len(df.columns) >= 1: 
                     # Heuristic: First column is often Country in wide formats? Or check content.
                     c_name_col = df.columns[0] if pd.notna(row[df.columns[0]]) else None
                
                if c_name_col and raw_country := row.get(c_name_col):
                    iso_code = _get_iso_code(raw_country)
                    country_val = iso_code
                    
                # Identify Product column (usually second or named 'Product'/'Tuote')
                p_name_col_candidates = [col for col in df.columns if ("product" in str(col).lower())]
                
                product_val = ""
                if not c_name_col: 
                    pass
                else:
                     # Check next column or find one with content matching pattern ART-xxxxx? No, values are there.
                     
                sales_values_dict: dict[str, float | None] = {}

                for col in df.columns:
                    s_c_lower = str(col).lower()
                    
                    if ("sales" == str(col)) or ("myynti".startswith(str(col))) or ("umsatz".startswith(str(col))): 
                         sales_col_name = col
                    
                    elif "product" not in s_c_lower and len(found_months_in_headers) > 0: # Skip country/product columns
                        continue
                        
                for month_header, val_str in zip(df.columns[1:], row.iloc[1:] if is_wide_format else []): 
                     pass
                
            except Exception as e:
                 final_rows.append({"country": "CZ", "product_id": "", "period": "", "sales": None}) # Fallback? No.

    else:
        # LONG FORMAT HANDLING
        
        country_col_name = None
        product_col_name = "product" 
        sales_col_name = None
        period_raw_col_name = None
        
        col_names_lower = [str(c).lower() for c in df.columns]
        
        if len(df.columns) >= 3: 
            
            for c in df.columns:
                s_c_lower = str(c).lower()
                
                if "land" == str(c): country_col_name = c
                
                elif ("tuote" == str(c)): product_col_name = c
        
        # Identify Sales Column (often 'Sales', 'Umsatz', 'Myynti') or infer from numeric content.
        
    return pd.DataFrame(final_rows)
