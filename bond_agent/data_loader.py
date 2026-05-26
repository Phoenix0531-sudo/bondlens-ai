from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "testdata.xlsx"
DEFAULT_LIVE_CACHE_PATH = PROJECT_ROOT / ".tmp" / "bond_spot_deal_snapshot.csv"

BOND_NAME = "债券简称"
MATURITY = "待偿期"
PRICE = "收盘净价(元)"
YIELD = "收盘到期收益率(%)"
WEIGHTED_YIELD = "加权收益率(%)"
VOLUME = "交易量(亿元)"
MATURITY_YEARS = "待偿期(年)"

NUMERIC_COLUMNS = [PRICE, YIELD, WEIGHTED_YIELD, VOLUME]
REQUIRED_COLUMNS = [BOND_NAME, MATURITY, PRICE, YIELD, WEIGHTED_YIELD, VOLUME]
LIVE_CHANGE_BP = "涨跌(BP)"
DATA_MODES = {"auto", "live", "static"}


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


def load_live_bond_data(fetcher=None, cache_path: str | Path | None = None, write_cache: bool = True) -> pd.DataFrame:
    if fetcher is None:
        import akshare as ak

        fetcher = ak.bond_spot_deal

    raw_df = fetcher()
    df = normalize_live_bond_data(raw_df)
    if write_cache:
        save_live_snapshot(df, cache_path=cache_path)
    return df


def normalize_live_bond_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    required = ["债券简称", "成交净价", "最新收益率", "加权收益率", "交易量"]
    missing = [column for column in required if column not in raw_df.columns]
    if missing:
        raise ValueError(f"Missing live bond columns: {', '.join(missing)}")

    df = pd.DataFrame()
    df[BOND_NAME] = raw_df["债券简称"].where(raw_df["债券简称"].notna(), "").astype(str).str.strip()
    df[MATURITY] = None
    df[PRICE] = pd.to_numeric(raw_df["成交净价"], errors="coerce")
    df[YIELD] = pd.to_numeric(raw_df["最新收益率"], errors="coerce")
    df[WEIGHTED_YIELD] = pd.to_numeric(raw_df["加权收益率"], errors="coerce")
    df[VOLUME] = pd.to_numeric(raw_df["交易量"], errors="coerce")
    if "涨跌" in raw_df.columns:
        df[LIVE_CHANGE_BP] = pd.to_numeric(raw_df["涨跌"], errors="coerce")
    df[MATURITY_YEARS] = None
    return df[df[BOND_NAME] != ""].copy()


def save_live_snapshot(df: pd.DataFrame, cache_path: str | Path | None = None) -> Path:
    snapshot_path = _live_cache_path(cache_path)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(snapshot_path, index=False, encoding="utf-8-sig")
    return snapshot_path


def load_live_snapshot(cache_path: str | Path | None = None, max_age_hours: float | None = None) -> tuple[pd.DataFrame, dict]:
    snapshot_path = _live_cache_path(cache_path)
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Live snapshot cache not found: {snapshot_path}")

    cached_at = datetime.fromtimestamp(snapshot_path.stat().st_mtime, timezone.utc)
    if max_age_hours is not None:
        age_hours = (datetime.now(timezone.utc) - cached_at).total_seconds() / 3600
        if age_hours > max_age_hours:
            raise ValueError(f"Live snapshot cache is stale: {age_hours:.2f} hours old")

    df = pd.read_csv(snapshot_path, encoding="utf-8-sig")
    for column in [PRICE, YIELD, WEIGHTED_YIELD, VOLUME, LIVE_CHANGE_BP, MATURITY_YEARS]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    if BOND_NAME in df.columns:
        df[BOND_NAME] = df[BOND_NAME].where(df[BOND_NAME].notna(), "").astype(str).str.strip()
    return df[df[BOND_NAME] != ""].copy(), {"snapshot_path": snapshot_path, "cached_at": cached_at}


def resolve_bond_data(
    mode: str = "static",
    path: str | Path | None = DEFAULT_DATA_PATH,
    live_fetcher=None,
    live_cache_path: str | Path | None = None,
    cache_max_age_hours: float | None = None,
) -> tuple[pd.DataFrame, dict]:
    data_path = path or DEFAULT_DATA_PATH
    cache_max_age = _cache_max_age_hours(cache_max_age_hours)
    normalized_mode = (mode or "static").lower()
    if normalized_mode not in DATA_MODES:
        raise ValueError(f"Unsupported bond data mode: {mode}. Choose from: {', '.join(sorted(DATA_MODES))}")

    if normalized_mode in {"auto", "live"}:
        try:
            df = load_live_bond_data(fetcher=live_fetcher, cache_path=live_cache_path)
            return df, _build_live_profile(df, requested_mode=normalized_mode)
        except Exception as exc:
            live_error = f"{type(exc).__name__}: {exc}"
            try:
                df, snapshot = load_live_snapshot(cache_path=live_cache_path, max_age_hours=cache_max_age)
                return df, _build_snapshot_profile(
                    df,
                    requested_mode=normalized_mode,
                    snapshot_path=snapshot["snapshot_path"],
                    cached_at=snapshot["cached_at"],
                    fallback_reason=live_error,
                )
            except Exception as snapshot_exc:
                fallback_reason = f"{live_error}; snapshot fallback failed: {type(snapshot_exc).__name__}: {snapshot_exc}"
            df = load_bond_data(data_path)
            return df, _build_static_profile(
                df,
                path=data_path,
                runtime_mode="static_fallback",
                requested_mode=normalized_mode,
                fallback_reason=fallback_reason,
            )

    df = load_bond_data(data_path)
    return df, _build_static_profile(df, path=data_path, runtime_mode="static_sample", requested_mode=normalized_mode)


def describe_data_source(path: str | Path = DEFAULT_DATA_PATH) -> dict:
    df = load_bond_data(path)
    return _build_static_profile(df, path=path, runtime_mode="static_sample", requested_mode="static")


def _build_static_profile(
    df: pd.DataFrame,
    path: str | Path = DEFAULT_DATA_PATH,
    runtime_mode: str = "static_sample",
    requested_mode: str = "static",
    fallback_reason: str | None = None,
) -> dict:
    data_path = Path(path)
    relative_path = data_path
    try:
        relative_path = data_path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        pass

    return {
        "source_id": "local_static_excel",
        "source_name": str(relative_path).replace("\\", "/"),
        "storage": "Excel workbook committed with the repository",
        "runtime_mode": runtime_mode,
        "requested_mode": requested_mode,
        "fetched_at": None,
        "fallback_reason": fallback_reason,
        "row_count": int(len(df)),
        "valid_yield_count": int(df[YIELD].notna().sum()),
        "columns": [BOND_NAME, MATURITY, PRICE, YIELD, WEIGHTED_YIELD, VOLUME],
        "active_live_feed": False,
        "active_live_snapshot": False,
        "provider": "repository",
        "legacy_crawler": {
            "path": "undergraduate-thesis-2024:data/Crawler.py",
            "status": "preserved_in_undergraduate_thesis_branch",
            "targets": [
                "http://company.cnstock.com/company/scp_gsxw/",
                "http://ggjd.cnstock.com/gglist/search/qmtbbdj/",
                "http://ggjd.cnstock.com/gglist/search/ggkx/",
            ],
            "notes": [
                "The current main branch does not include, import, or call this crawler.",
                "The legacy crawler depends on MongoDB and thesis-era text analysis modules.",
                "Legacy CNSTOCK endpoints are not treated as a reliable live data source.",
            ],
        },
        "limitations": [
            "Static repository sample, not real-time market data.",
            "No issuer rating, credit event, macro curve, or news feed is attached.",
            "Use results as an engineering demo and evidence-grounded sample analysis only.",
        ],
    }


def _build_live_profile(df: pd.DataFrame, requested_mode: str) -> dict:
    return {
        "source_id": "akshare_bond_spot_deal",
        "source_name": "AkShare bond_spot_deal",
        "provider": "AKShare public financial data interface",
        "target_url": "https://www.chinamoney.com.cn/chinese/mkdatabond/",
        "storage": "Fetched at request time; not persisted",
        "runtime_mode": "live",
        "requested_mode": requested_mode,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "fallback_reason": None,
        "row_count": int(len(df)),
        "valid_yield_count": int(df[YIELD].notna().sum()),
        "columns": [BOND_NAME, MATURITY, PRICE, YIELD, WEIGHTED_YIELD, VOLUME, LIVE_CHANGE_BP],
        "active_live_feed": True,
        "active_live_snapshot": False,
        "legacy_crawler": {
            "path": "undergraduate-thesis-2024:data/Crawler.py",
            "status": "preserved_in_undergraduate_thesis_branch",
        },
        "limitations": [
            "Public live endpoint availability depends on third-party source stability and trading session.",
            "bond_spot_deal does not provide maturity, issuer rating, credit events, or macro curve fields.",
            "Use live results as market monitoring evidence, not investment advice.",
        ],
    }


def _build_snapshot_profile(
    df: pd.DataFrame,
    requested_mode: str,
    snapshot_path: Path,
    cached_at: datetime,
    fallback_reason: str,
) -> dict:
    relative_path = snapshot_path
    try:
        relative_path = snapshot_path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        pass

    return {
        "source_id": "akshare_bond_spot_deal_snapshot",
        "source_name": "Cached AkShare bond_spot_deal snapshot",
        "provider": "AKShare public financial data interface",
        "target_url": "https://www.chinamoney.com.cn/chinese/mkdatabond/",
        "storage": str(relative_path).replace("\\", "/"),
        "runtime_mode": "live_snapshot",
        "requested_mode": requested_mode,
        "fetched_at": cached_at.isoformat(),
        "fallback_reason": fallback_reason,
        "row_count": int(len(df)),
        "valid_yield_count": int(df[YIELD].notna().sum()),
        "columns": [BOND_NAME, MATURITY, PRICE, YIELD, WEIGHTED_YIELD, VOLUME, LIVE_CHANGE_BP],
        "active_live_feed": False,
        "active_live_snapshot": True,
        "legacy_crawler": {
            "path": "undergraduate-thesis-2024:data/Crawler.py",
            "status": "preserved_in_undergraduate_thesis_branch",
        },
        "limitations": [
            "Live fetch failed, so this answer uses the most recent local live-data snapshot.",
            "Snapshot freshness depends on the last successful AkShare request.",
            "Issuer rating, credit events, macro curve, and full security master fields are still not attached.",
        ],
    }


def _live_cache_path(cache_path: str | Path | None = None) -> Path:
    configured = cache_path or os.environ.get("BOND_LIVE_CACHE_PATH")
    return Path(configured) if configured else DEFAULT_LIVE_CACHE_PATH


def _cache_max_age_hours(value: float | None) -> float | None:
    if value is not None:
        return value
    configured = os.environ.get("BOND_LIVE_CACHE_MAX_AGE_HOURS")
    return float(configured) if configured else 24.0


def records_from_frame(df: pd.DataFrame, limit: int = 10) -> list[dict]:
    display_columns = [BOND_NAME, MATURITY, MATURITY_YEARS, PRICE, YIELD, WEIGHTED_YIELD, VOLUME, LIVE_CHANGE_BP]
    available_columns = [column for column in display_columns if column in df.columns]
    records = df[available_columns].head(limit).where(pd.notnull(df[available_columns]), None)
    return records.to_dict(orient="records")
