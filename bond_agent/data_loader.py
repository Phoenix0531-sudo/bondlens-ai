from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "testdata.xlsx"

BOND_NAME = "债券简称"
MATURITY = "待偿期"
PRICE = "收盘净价(元)"
YIELD = "收盘到期收益率(%)"
WEIGHTED_YIELD = "加权收益率(%)"
VOLUME = "交易量(亿元)"
MATURITY_YEARS = "待偿期(年)"

NUMERIC_COLUMNS = [PRICE, YIELD, WEIGHTED_YIELD, VOLUME]
REQUIRED_COLUMNS = [BOND_NAME, MATURITY, PRICE, YIELD, WEIGHTED_YIELD, VOLUME]


def parse_maturity_to_years(value: object) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).strip().upper()
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([YMD]?)", text)
    if not match:
        return None

    amount = float(match.group(1))
    unit = match.group(2) or "Y"
    if unit == "Y":
        return amount
    if unit == "M":
        return amount / 12
    if unit == "D":
        return amount / 365
    return None


def load_bond_data(path: str | Path = DEFAULT_DATA_PATH) -> pd.DataFrame:
    data_path = Path(path)
    if not data_path.exists():
        raise FileNotFoundError(f"Bond data file not found: {data_path}")

    df = pd.read_excel(data_path, header=1)
    df.columns = [str(column).strip() for column in df.columns]

    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    df = df.dropna(subset=[BOND_NAME]).copy()
    df[BOND_NAME] = df[BOND_NAME].astype(str).str.strip()
    df[MATURITY_YEARS] = df[MATURITY].map(parse_maturity_to_years)

    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    return df


def records_from_frame(df: pd.DataFrame, limit: int = 10) -> list[dict]:
    display_columns = [BOND_NAME, MATURITY, MATURITY_YEARS, PRICE, YIELD, WEIGHTED_YIELD, VOLUME]
    available_columns = [column for column in display_columns if column in df.columns]
    records = df[available_columns].head(limit).where(pd.notnull(df[available_columns]), None)
    return records.to_dict(orient="records")
