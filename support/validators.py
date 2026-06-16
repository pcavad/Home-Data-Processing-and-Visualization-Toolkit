import os
import pandas as pd
from datetime import datetime
from pydantic import Field, AfterValidator
from typing import Dict, List, Any, Annotated, Optional

from .config import DATE_FMT, CLASSIFICATIONS

# ---------------------------
# Generic types
# ---------------------------


PositiveInt = Annotated[int, Field(ge=0)]

# # Pandas dataframe
# def check_df(df: pd.DataFrame) -> pd.DataFrame:
#     if not isinstance(df, pd.DataFrame):
#         raise ValueError("Invalid dataframe")
#     return df

# ValidatedDF = Annotated[pd.DataFrame, AfterValidator(check_df)]

# ---------------------------
# Custom built types
# ---------------------------

# Valid classifications
def validate_classification(v: Optional[str]) -> Optional[str]:
    if v is not None and v not in CLASSIFICATIONS:
        raise ValueError(f"classification deve essere uno tra {CLASSIFICATIONS} oppure None, ricevuto: '{v}'")
    return v


# ---------------------------
# File and dir
# ---------------------------

# def require_file(path: str, msg: str):
#         if not os.path.exists(path):
#             raise FileNotFoundError(msg)

# def require_directory(path: str):
#     """Verifica che una directory esista."""
#     if not os.path.exists(path):
#         raise FileNotFoundError(f"Directory does not exist: {path}")

# ---------------------------
# Dates
# ---------------------------
def validate_date_format(v: str) -> str:
    try:
        datetime.strptime(v, DATE_FMT)
    except ValueError:
        raise ValueError(f"deve essere una data valida nel formato {DATE_FMT} (ricevuto: '{v}')")
    return v

def check_date_range(start, end):
    """Verifica che start date sia inferiore a end date"""
    if end <= start:
        raise ValueError(
            f"end_date ({end}) deve essere successiva a start_date ({start})"
        )