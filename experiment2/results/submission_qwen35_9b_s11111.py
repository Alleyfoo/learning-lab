import re
from pathlib import Path
import pandas as pd


def normalize(source_path: str) -> pd.DataFrame:
    """Normalize sales data from various formats into canonical form."""
    
    try:
        df = pd.read_csv(source_path, dtype=str).copy()
    except Exception:
         raise Escalate("Cannot read source file", {})

    if len(df) == 0 or (len(df.columns) < 2): 
        return pd.DataFrame(columns=["country","product_id","period","sales"])

# Identify columns by checking for known keywords in column names.
    
# Let's assume the following:
# - If a column name contains 'month'/'kausi', it is period (or part of wide format).
# - If a column name contains 'january' etc., it is sales/period combined? No, usually separate year/month or just month.

    # Identify columns by checking for specific patterns in column names
    
def normalize(source_path):
   import pandas as pd
   
   df = pd.read_csv(source_path).copy()

# I will now write the final code block that handles all cases robustly.
