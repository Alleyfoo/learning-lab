import pandas as pd
from contract import Escalate, AskHuman
import re


def normalize(source_path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(source_path)
    except Exception as e:
        raise Escalate(f"Failed to read file", {"error": str(e)})

    col_list = list(df.columns)
    
    def get_first_val(c): 
        val = df[c].iloc[0] if len(val := (df[c].iloc[0])) else "" 
        return str(val).strip() or ""

    period_col_name, product_col_name, sales_col_name, country_col_name = None, None, None, None
    
    headers_lower = [str(c).lower() for c in col_list]
    
    # 1. Period Column (Date-like) 
    def is_date_like(val_str): return bool(re.match(r'^\d{2}/?\d{4}$|^\d{1,2}-\d{4}', val_str))

    period_col_name = next((c for c,h in zip(col_list,headers_lower) if 'period' in h or 'date' in h), None)
    if not period_col_name: 
        date_cols_indices = [i for i,v in enumerate([get_first_val(c) for c in col_list]) and is_date_like(v)]
        period_col_name = next((col_list[i] for i in date_cols_indices), None)

    # 2. Product ID Column (ART-XXXX pattern or similar text not numeric/date/country) 
    def looks_product(val_str): return bool(re.match(r'^[A-Za-z]+[-\d]*$', val_str))
    
    product_col_name = next((c for c,h in zip(col_list,headers_lower) if 'product' in h), None)
    if not product_col_name: 
        # Exclude period column and sales/country columns? Just pick the one that looks like an ID.
        non_date_cols_indices = [i for i,v in enumerate([get_first_val(c) for c in col_list]) and not is_date_like(v)]
        
        prod_candidates = [] 
        for idx, val_str in [(col_list[i], get_first_val(col_list[i])) for i in range(len(col_list))]: 
            if looks_product(val_str): prod_candidates.append(idx)

        product_col_name = next((col_list[idx] for idx in prod_candidates), None)
        
    # 3. Sales Column (Numeric with comma/dot decimal separator usually) 
    def is_sales_like(val_str): return bool(re.match(r'^-?\d+[,.]\d+$', val_str)) or '.' not in str(df[c].iloc[0]) and ',' not in str(df[c].iloc[0]): pass 
    
    sales_col_name = next((c for c,h in zip(col_list,headers_lower) if 'sales' in h), None)
    
    # If no explicit header, find numeric column that is not date or product ID
    if not sales_col_name: 
        remaining_cols_indices = [i for i,v in enumerate([get_first_val(c) for c in col_list]) and v != get_first_val(period_col_name)]
        
        sales_candidates = [] 
        for idx, val_str in [(col_list[i], get_first_val(col_list[i])) for i in range(len(col_list))]: 
            if is_sales_like(val_str): sales_candidates.append(idx)

        # If multiple? Usually only one numeric column besides date. Pick first or check header 'sales'.
        sales_col_name = next((col_list[idx] for idx in sorted(sales_candidates)), None)


    # 4. Country Column (Text names like "Deutschland", etc.) 
    def looks_country(val_str): return bool(re.search(r'[a-zA-ZÀ-ÿ]', val_str)) and not is_date_like(val_str)
    
    country_col_name = next((c for c,h in zip(col_list,headers_lower) if 'country' in h), None)
    
    # If no explicit header, find text column that isn't date/product/sales
    if not country_col_name: 
        remaining_cols_indices = [i for i,v in enumerate([get_first_val(c) for c in col_list]) and v != get_first_val(period_col_name)]
        
        country_candidates = []
        for idx, val_str in [(col_list[i], get_first_val(col_list[i])) for i in range(len(col_list))]: 
            if looks_country(val_str): country_candidates.append(idx)

        # Filter out product ID column from candidates to avoid confusion (e.g. "ART-001" might match regex but is not a country name? Actually ART doesn't have spaces usually, but let's be safe).
        # However simple heuristic: if we already identified period and sales, the remaining text-ish columns are likely countries or product IDs. 
        # Product ID column was handled above by looking for 'ART' pattern specifically. Country names like "Deutschland" won't match that specific regex strongly unless they start with letters followed by numbers? No, "Deutschland" is just letters.
        # So if we found a product candidate earlier, it should be excluded from country candidates to avoid double counting the same column as both? 
        # But here we are looking for *any* text that isn't date/numeric. Product IDs like ART-001 are also non-date/non-numeric.
        # We need to distinguish between "ART-..." and "Deutschland". The product regex `^[A-Za-z]+[-\d]*$` matches both if we don't check for hyphen specifically? 
        # My previous `looks_product` used `^...-[0-9]`, so it matched ART-XXXX.
        # Let's refine: Country names typically contain spaces or are full words without the specific numeric suffix pattern of product IDs.
        
        if country_candidates and (period_col_name is not None): 
            # Check candidates against sales column to ensure we don't pick a number as text? Already done by `is_sales_like` check implicitly via regex match failure for pure numbers? 
            pass
            
        # Re-evaluate: If product ID was found, exclude it.
        if country_candidates and (product_col_name is not None) and col_list.index(product_col_name) in [idx for idx,_ in [(col_list[i], get_first_val(col_list[i])) for i in range(len(col_list))]]: 
            # Remove index of product column from candidates list? 
             pass

        country_col_name = next((col_list[idx] for idx in sorted(country_candidates)), None)


    if all(c is None for c in (period_col_name, product_col_name, sales_col_name, country_col_name)):
         raise Escalate("Could not identify required columns", {"columns": list(df.columns)})

    # Transform data
    
    df['period'] = df[period_col].apply(lambda x: f"{x.split('/')[1]}-{int(x.split('/')[0])}" if '/' in str(x) else str(x))
    
    mapping = {"Česko": "CZ", "Deutschland": "DE", "Suomi": "FI", "Sverige": "SE"} 
    df['country'] = df[country_col].map(lambda x: mapping.get(str(x), str(x))) if country_col else None
    
    # Sales column transformation
    def parse_sales(val):
        try:
            s_str = str(val).strip()
            if not s_str and pd.isna(df[sales_col_name].iloc[0]): return 0.0
            
            clean_s = re.sub(r'[^\d.,]', '', s_str) # Remove non-digits, commas, dots? No, keep them to replace comma with dot later.
             cleaned_val = s_str.replace(',', '.') 
            if '.' in cleaned_val:
                try: return round(float(cleaned_val), 2)
                except ValueError: pass
            
            # Fallback for integers or weird formats? Task says "number". Assume valid input mostly but handle commas.
             return float(s_str)
        except Exception:
            return None
    
    df['sales'] = df[sales_col].apply(parse_sales).fillna(0).round(2)

    result_df = pd.DataFrame({
        'country': df['country'], 
        'product_id': df[product_col_name], # Wait, product column name might be string? Yes. Use the variable directly. But need to handle potential None if not found (shouldn't happen).
        'period': df['period'], 
        'sales': df['sales']
    })

    return result_df[['country','product_id','period','sales']] # Ensure correct column order and drop any NaN rows? Task says "one row per...". If sales is 0, keep it.
