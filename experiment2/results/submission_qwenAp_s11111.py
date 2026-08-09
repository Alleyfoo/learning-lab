import pandas as pd
from contract import Escalate, AskHuman


def normalize(source_path: str) -> pd.DataFrame:
    """
    Normalize sales data from various partner formats into a canonical DataFrame.
    
    Output columns:
      - country   (two-letter uppercase code)
      - product_id (as issued)
      - period    (YYYY-MM format string)
      - sales     (numeric, rounded to 2 decimals)
    """

    # Mapping from local names to ISO-3166 alpha-2 codes.
    COUNTRY_MAP = {
        "Česko": "CZ",
        "Deutschland": "DE",
        "Suomi": "FI",
        "Sverige": "SE",
    }

    def parse_period(s: str) -> str:
        """Convert 'MM/YYYY' or similar to 'YYYY-MM'."""
        s = s.strip()
        if "/" in s and len(s.split("/")) == 2:
            parts = s.split("/")
            month, year = parts[0], parts[1]
            return f"{year}-{month}"
        elif "-" in s and len(s.split("-")) >= 2:
            # Already looks like YYYY-MM or similar; just normalize.
            parts = s.split("-")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                return f"{parts[0]}-{parts[1]}"
        raise Escalate("Unable to parse period from source", {"value": s})

    def normalize_country(name: str):
        if name in COUNTRY_MAP:
            return COUNTRY_MAP[name]
        # If unknown, we must escalate. We cannot invent a code or ask human for something present.
        raise Escalate(f"Unknown country name not found in mapping", {"name": name})

    def normalize_sales(s_str: str) -> float:
        s = s_str.strip().strip('"')  # remove surrounding quotes if any
        try:
            return round(float(s.replace(",", ".")), 2)
        except ValueError:
            raise Escalate("Unable to parse sales value", {"value": s})

    df = pd.read_csv(source_path, dtype=str)
    
    required_cols_inferred = ["period", "product_id", "country_name", "sales"] # tentative names from example header
    
    if set(df.columns).issubset(required_cols_inferred):
        cols_to_use = list(set(required_cols_inferred))
        df_sel = df[cols_to_use].copy()
        
        # Normalize country column name (if present as 'maa')
        col_map = {col: "country" for col in ["maa", "land", "nation"]}  # generic guess; adjust based on actual header
        
        if not set(df.columns).issubset(["period", "product_id", "sales"]):
            raise Escalate("Missing required columns (period, product_id, sales) or extra unknowns that block normalization.", {})

    df_sel = pd.read_csv(source_path)  # re-read to handle dynamic column detection safely
    
    if not {"period" in set(df.columns)}:
        raise Escalate("Column 'period' missing", {}), AskHuman(...)
    
    # Normalize country names using the map; unknown -> escalate.
    df_sel["country"] = df_sel["country"].apply(normalize_country)

    # Parse period to YYYY-MM format
    try:
        df_sel["period"] = df_sel["period"].apply(parse_period)
    except Escalate as e:
        raise
    
    # Normalize sales values (strip quotes, handle commas)
    def clean_sales(val):
        if isinstance(val, str):
            return normalize_sales(val)
        elif isinstance(val, float):
            return round(float(format(val, ".2f")), 2)
        else:
            raise Escalate(f"Unexpected sales value type", {"value": val})

    df_sel["sales"] = df_sel["sales"].apply(clean_sales).round(2)

    # Ensure final canonical column order and types
    result_df = pd.DataFrame({
        "country": df_sel["country"],
        "product_id": df_sel["product_id"],
        "period": df_sel["period"],
        "sales": df_sel["sales"]
    })

    return result_df
