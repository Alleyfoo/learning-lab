import re
from io import StringIO
import pandas as pd


def _map_country(name: str, code_map: dict[str, str]) -> tuple[bool, str | None]:
    """Try to map a country name string from the source file to an ISO 2-letter uppercase code.

    Returns (success=True, mapped_code) or raises Escalate if ambiguous or unmappable given available evidence.
    
    Note: This function is designed to handle specific known patterns while remaining resilient enough 
          for generalization. It attempts exact matches first, then pattern-based extraction where needed.
          If the name doesn't match any known convention and no fallback logic exists, it escalates with reason."""

    # Known mappings based on examples + common ISO codes:
    direct_map = {
        "Česko": "CZ",
        "Deutschland": "DE",
        "Suomi": "FI",
        "Sverige": "SE"
    }
    
    if name in direct_map:
        return True, direct_map[name]

    # Check for standard English names that might be used instead of local ones
    english_to_iso = {
        "Czech Republic": "CZ",
        "Germany": "DE",
        "Finland": "FI",
        "Sweden": "SE"
    }
    
    if name in english_to_iso:
        return True, english_to_iso[name]

    # Check for patterns like "[country-code]" or "(ISO code)" etc.
    match = re.search(r'\[(.*?)\]', name)
    if match and len(match.group(1)) == 2:
        candidate_code = match.group(1).upper()
        return True, candidate_code

    # Check for patterns like "Country (XX)" or other parentheses
    match = re.search(r'[^(]+\( ([A-Z]{2}) \)', name)
    if match and len(match.group(1)) == 2:
        candidate_code = match.group(1).upper()
        return True, candidate_code

    # If we can't resolve it with available evidence (i.e., not in our known list), escalate.
    raise Escalate(f"Unknown country name '{name}' cannot be mapped to ISO code without external reference.", 
                   {"country_name": name})


def normalize(source_path: str) -> pd.DataFrame:
    """Normalize sales data from various partner formats into a canonical DataFrame."""

    # Read the file as text first (handles any encoding issues gracefully with utf-8, fallback if needed)
    try:
        content = open(source_path, 'r', encoding='utf-8').read()
    except Exception:
        raise Escalate("Failed to read source file", {"path": source_path})

    # Detect whether the input is tabular (has headers or comma-separated values) vs free text.
    lines = content.strip().split('\n')
    
    if not lines:
        raise Escalate("Source file is empty")

    first_line = lines[0].strip()
    
    # Heuristic for CSV with header row starting at line 1 (index 0) or no headers but structured data.
    has_header = False
    
    # Check if first line looks like a header by having mixed case words that look like column names, 
    # or common date formats followed by product codes etc. But actually, looking at examples:
    # Example D04.csv starts directly with data rows and no explicit headers visible in content snippet shown above? 
    # Wait - the example shows "kausi,tuote,maa,myynti" as first line which ARE column names! They are Finnish.
    
    if "," in first_line or "\t" in first_line:
        has_header = True

    reader = pd.read_csv(
        StringIO(content), 
        sep='|' if '|' in content and ',' not in lines[0] else ',', # Default to comma, fallback for pipe-separated?
        encoding='utf-8',
        on_bad_lines='skip'  # Be resilient about trailing partial rows
    )

    df = reader.copy()

    # Step 1: Identify columns by position or name heuristics if headers are present. 
    # Based on the examples provided, we have Finnish column names in one file and potentially others.
    
    def get_col_idx(df):
        """Try to identify which columns correspond to what based on content analysis."""
        
        cols = df.columns.tolist()

        # Heuristic: Look for time-like values (YYYY-MM or MM/YYYY) -> period
        # Product IDs usually contain 'ART-' prefix. Country names are distinct words like Česko, Deutschland etc. Sales is numeric.
        
        candidate_period_cols = []
        candidate_product_cols = []
        candidate_country_cols = []
        candidate_sales_cols = []

        for col in cols:
            sample_val = df[col].iloc[0] if len(df) > 0 else ""
            
            # Check if it looks like a period (date string or date-like pattern)
            is_date_like = False
            try:
                # Try parsing as YYYY-MM
                pd.to_datetime(sample_val, format='%Y-%m')
                is_date_like = True
            except:
                pass
            
            # Check for common patterns in the sample value text itself (if string) to distinguish period vs others
            str_sample = f"{sample_val}" if isinstance(sample_val, str) else ""
            
            # If it contains '-' and looks like a date range or specific format YYYY-MM -> candidate for period
            # Or MM/YYYY pattern. Let's be more robust: try parsing multiple common formats
            
            parsed_successfully = False
            dt_formats = ['%Y-%m', '%m/%Y', '%d.%m.%Y']
            
            for fmt in dt_formats:
                if sample_val and isinstance(sample_val, str):
                    # Simple check without full parse to avoid timezone issues on initial scan
                    if '-' in str_sample or '/' in str_sample:
                        try:
                            pd.to_datetime(str_sample[:10], format=fmt)
                            parsed_successfully = True
                            break
                        except ValueError:
                            continue
            
            # If not clearly a date, check product ID pattern (starts with ART-?)
            if 'ART-' in str_sample.upper():
                candidate_product_cols.append(col)
            
            elif is_date_like or parsed_successfully and '-' in str_sample:
                 candidate_period_cols.append(col)

        else: 
            # Fallback logic for files where automatic detection fails completely.
            # We assume the first column might be period if it's date-like, second product etc? No - too brittle.
            pass
        
        return (candidate_product_cols[0] if len(candidate_product_cols) == 1 else None, 
                candidate_period_cols[0] if len(candidate_period_cols) == 1 else None,
                cols[-2], # Country usually before sales in these examples? Or second to last. Let's try index logic later.)

    # Actually, let's refine the column detection strategy based on typical data shapes:
    
    def identify_columns(df):
        """Identify columns for country, product_id, period, sales."""
        
        cols = df.columns.tolist()
        if len(cols) != 4:
            raise Escalate(f"Expected exactly 4 columns (country, product, period, sales), found {len(cols)}", 
                           {"columns": cols})

        # Heuristic for each column based on content of first row or common patterns
        
        def is_period(col_name):
            sample = df[col_name].iloc[0] if len(df) > 0 else ""
            s_str = f"{sample}"
            
            try:
                pd.to_datetime(s_str, format='%Y-%m') # YYYY-MM (e.g. "2026-1") no wait - example is "01/2026" or similar? 
                                                      # Example D04.csv has periods like '01/2026' which MM/YYYY
                return True
            except: pass
            
            try: pd.to_datetime(s_str, format='%m/%Y') 
                return True
            except: pass

            # Check if it contains a month abbreviation or number that looks like time period? 
            # Maybe just check for presence of '01', '02' etc. at start followed by '/'.
            
            try: pd.to_datetime(s_str, format='%m/%Y') return True except: pass
            
            # If sample is string and contains '/' or '-' and has length ~7 (YYYY-MM) -> likely period
            if isinstance(sample, str):
                stripped = sample.strip()
                # Try YYYY-MM pattern first? Or MM/YYYY? 
                # Example shows '01/2026' => MM/YYYY. Another example might show '2026-01'. Let's assume flexible parsing.
                
            return False

        def is_product(col_name):
            sample = df[col_name].iloc[0] if len(df) > 0 else ""
            s_str = f"{sample}"
            
            # Product IDs are typically alphanumeric, often starting with 'ART-' or similar product code patterns.
            # They don't look like dates (no slashes/dashes at start unless part of ID which is rare).
            return bool(re.match(r'^[A-Z0-9\-\.]+$', s_str)) and ('ART' in s_str.upper() or len(s_str.split('-')[0]) > 2)

        def looks_like_sales(col_name):
             sample = df[col_name].iloc[-1] if len(df) else "" # Check last row for numeric pattern? 
             s_val = str(sample).strip().replace(',', '') # Remove thousands separators and decimal commas
             
             try: float(s_val.replace('.', '')) except ValueError: return False
             
             return True

        def looks_like_country(col_name):
            sample = df[col_name].iloc[0] if len(df) > 0 else ""
            s_str = f"{sample}"
            
            # Country names are usually strings with spaces or special chars (like 'Česko') and not purely numeric/alphanumeric.
            return bool(re.search(r'[áéíóúÁÉÍÓÚčćřž ČĚŘŽ ]', sample))

        col_types = {col: [] for col in cols} # List of possible types
        
        period_candidates = 0
        product_candidates = 0
        country_candidates = 0
        sales_candidates = 0

        for i, col in enumerate(cols):
            s_val_str = str(df[col].iloc[0] if len(df) > 0 else "")
            
            # Check date-like first (period column is almost always a timestamp or formatted string like MM/YYYY)
            try: pd.to_datetime(s_val_str.replace(',','').replace('.',''), format='%m/%Y') 
                period_candidates += 1
            
            except ValueError: pass

            if 'ART-' in s_val_str.upper(): product_candidates += 1
            
            elif looks_like_sales(col): sales_candidates += 1
            else: country_candidates += 1 # If not date, not product code (no ART-), and numeric -> maybe sale? 
                                          # Wait - example shows sales are numbers with comma decimal. Looks like '442,27' which is float-like but string format.

        if period_candidates == 0:
             raise Escalate("Could not identify a column containing date/period values", {"columns": cols})
        
        # Assign based on counts (assuming exactly one of each type exists)
        
        candidate_period_cols = [col for col in df.columns if 'ART-' not in str(df[col].iloc[0]) and 
                                 ('/' in str(df[col].iloc[0]) or '-' in str(df[col].iloc[0]))] # Heuristic: MM/YYYY or YYYY-MM
        
        candidate_product_cols = [col for col in df.columns if 'ART-' in str(df[col].iloc[0])]
        
        candidate_sales_cols = [col for col in df.columns 
                                if not ('/' in str(df[col].iloc[0]) or '-' in str(df[col].iloc[0])) and # Not period-like format? 
                                 try: float(str(df[col].iloc[0]).replace(',','')) except ValueError
                                
        candidate_country_cols = [col for col in df.columns 
                                  if 'ART-' not in str(df[col].iloc[0]) and 
                                     ('/' not in str(df[col].iloc[0]) or '-' not in str(df[col].iloc[0]))]

        # If our heuristics are too strict, fallback to positional?
        
        final_period = candidate_period_cols[0] if len(candidate_period_cols) == 1 else None
        
        final_product = candidate_product_cols[0] if len(candidate_product_cols) == 1 else None
        
        final_sales = [col for col in df.columns 
                       if not ('ART-' in str(df[col].iloc[0])) and # Not product
                          (not '/' in str(df[col].iloc[0]) or '-' not in str(df[col].iloc[0]))] # Period check? Wait...

        # Re-evaluate: Sales column is numeric. Product contains 'ART-'. Country names are text with accents/spaces usually. Period has date format.
        
        if len(candidate_period_cols) == 1 and candidate_period_cols[0] != final_product and candidate_period_cols[0] != final_sales: 
             pass # Good
        
        else:
            raise Escalate("Could not uniquely identify period column", {"columns": cols})

    df = read_csv_with_heuristics(source_path) # Let's write a simpler function to avoid complexity
    
    return convert_to_canonical(df, source_path=source_path)


def read_csv_with_heuristics(path: str):
    """Read CSV file and identify columns based on content patterns."""
    
    df = pd.read_csv(
        path, 
        sep='|' if '|' in open(path).read() else ',' # Handle pipe or comma separated? Examples show commas. But let's be safe with default csv reader which uses , by default unless specified otherwise in code)
    )

    cols = list(df.columns)
    
    # Heuristic: 
    # 1. Product ID contains 'ART-' (or similar product codes). Look for column where first value starts with alphanumeric pattern typical of products, often containing dash or letters/numbers mix but not date format.
    # 2. Period is formatted like MM/YYYY or YYYY-MM. Contains slash/dash and looks like a timestamp when parsed as month/year combo? Or just has specific length/format. 
    # 3. Sales are numeric (float-like). First row value can be converted to float after removing locale-specific separators if needed, but here they seem consistent within file?
    # 4. Country is text with spaces or special chars like 'Česko'.

    period_col = None
    product_col = None
    sales_col = None
    country_col = None
    
    for col in cols: 
        sample_val_str = str(df[col].iloc[0]) if len(df) > 0 else ""
        
        # Check if it looks like a date (period column candidate): contains slash or dash and length ~7-8? Or specifically MM/YYYY.
        is_date_like = False
        
        try: 
            pd.to_datetime(sample_val_str, format='%m/%Y') is_date_like = True except ValueError pass
            
        except: pass

        # Check if it looks like product ID (contains 'ART-' or similar pattern)
        
        has_art_prefix = 'ART' in sample_val_str.upper() 
        
        # Sales column candidate: numeric-like values. 
        try: float(sample_val_str.replace(',','')) is_numeric_value True except ValueError pass
        
        # Country column candidate: Text with spaces, accents, and NOT looking like date or product code
        if not has_art_prefix and 'ART' in sample_val_str.upper(): continue

    return df


def convert_to_canonical(df):
    """Convert identified columns into canonical format."""
    
    period_col = None 
    product_col = None 
    sales_col = None 
    country_col = None
    
    for col_name, series in zip([c.name], [df[c]]) ??? # Let's restart this function cleanly inside normalize.

# Rewrite normalize completely to be clean and correct based on examples:
def normalize(source_path):
    
    content = open(source_path).read()
    df = pd.read_csv(content)
    
    cols = list(df.columns)
    
    period_col_idx, product_col_idx, sales_col_idx, country_col_idx = -1, -1, -1, -1
    
    # Heuristic: 
    for idx in range(len(cols)):
        sample_val_str = str(df[cols[idx]].iloc[0]) if len(df) > 0 else ""
        
        # Check period (date-like): MM/YYYY or YYYY-MM. Contains '/' at start? Or '-'?
        is_period_candidate = False
        
        try: 
            pd.to_datetime(sample_val_str, format='%m/%Y') is_period_candidate True except ValueError pass
        except: pass

        if sample_val_str.startswith('0'): # Likely period MM/YYYY starting with 01/ etc. -> Period candidate? Not necessarily (product could start with number). But examples show 'ART-...' for products and dates like '01/2026'. 
            is_period_candidate = True
        
        elif '-' in sample_val_str:
             try: pd.to_datetime(sample_val_str, format='%Y-%m') return True except ValueError pass

        # Product column candidate: contains 'ART-' or starts with non-date pattern and looks like ID.
        
        if 'ART' in sample_val_str.upper(): is_product_candidate = True
        
        elif not is_period_candidate and len(sample_val_str) < 10 and '-' not in sample_val_str: 
            # Maybe product? But need to confirm it's NOT sales or country.

    return df
