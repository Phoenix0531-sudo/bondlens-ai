from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from .data_loader import (
    BOND_NAME,
    MATURITY,
    MATURITY_YEARS,
    PRICE,
    VOLUME,
    WEIGHTED_YIELD,
    YIELD,
    load_bond_data,
    records_from_frame,
)


RANK_COLUMNS = {
    "yield": YIELD,
    "收益率": YIELD,
    "volume": VOLUME,
    "成交量": VOLUME,
    "maturity": MATURITY_YEARS,
    "期限": MATURITY_YEARS,
    "price": PRICE,
    "净价": PRICE,
}


def _summary(series: pd.Series) -> dict:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return {"count": 0}

    return {
        "count": int(clean.count()),
        "mean": round(float(clean.mean()), 4),
        "std": round(float(clean.std(ddof=0)), 4),
        "min": round(float(clean.min()), 4),
        "p25": round(float(clean.quantile(0.25)), 4),
        "median": round(float(clean.median()), 4),
        "p75": round(float(clean.quantile(0.75)), 4),
        "max": round(float(clean.max()), 4),
    }


def search_bonds(
    name: str | None = None,
    min_maturity: float | None = None,
    max_maturity: float | None = None,
    min_yield: float | None = None,
    max_yield: float | None = None,
    limit: int = 20,
    data_path: str | None = None,
) -> dict:
    df = load_bond_data(data_path) if data_path else load_bond_data()

    if name:
        df = df[df[BOND_NAME].str.contains(name, case=False, na=False)]
    if min_maturity is not None:
        df = df[df[MATURITY_YEARS] >= min_maturity]
    if max_maturity is not None:
        df = df[df[MATURITY_YEARS] <= max_maturity]
    if min_yield is not None:
        df = df[df[YIELD] >= min_yield]
    if max_yield is not None:
        df = df[df[YIELD] <= max_yield]

    return {
        "tool": "search_bonds",
        "criteria": {
            "name": name,
            "min_maturity": min_maturity,
            "max_maturity": max_maturity,
            "min_yield": min_yield,
            "max_yield": max_yield,
            "limit": limit,
        },
        "match_count": int(len(df)),
        "records": records_from_frame(df.sort_values(YIELD, ascending=False), limit),
    }


def describe_market(data_path: str | None = None) -> dict:
    df = load_bond_data(data_path) if data_path else load_bond_data()
    yield_data = pd.to_numeric(df[YIELD], errors="coerce").dropna()
    bins = pd.cut(yield_data, bins=5).value_counts().sort_index()

    return {
        "tool": "describe_market",
        "sample_count": int(len(df)),
        "columns": [BOND_NAME, MATURITY, PRICE, YIELD, WEIGHTED_YIELD, VOLUME],
        "yield_summary": _summary(df[YIELD]),
        "weighted_yield_summary": _summary(df[WEIGHTED_YIELD]),
        "volume_summary": _summary(df[VOLUME]),
        "maturity_summary_years": _summary(df[MATURITY_YEARS]),
        "yield_distribution": {str(interval): int(count) for interval, count in bins.items()},
    }


def rank_bonds(
    by: str = "yield",
    top_n: int = 10,
    ascending: bool = False,
    data_path: str | None = None,
) -> dict:
    df = load_bond_data(data_path) if data_path else load_bond_data()
    column = RANK_COLUMNS.get(by, by)
    if column not in df.columns:
        allowed = ", ".join(sorted(RANK_COLUMNS))
        raise ValueError(f"Unsupported ranking column: {by}. Allowed keys: {allowed}")

    ranked = df.dropna(subset=[column]).sort_values(column, ascending=ascending)
    return {
        "tool": "rank_bonds",
        "rank_by": column,
        "ascending": ascending,
        "top_n": top_n,
        "records": records_from_frame(ranked, top_n),
    }


def detect_yield_outliers(
    method: str = "zscore",
    threshold: float = 3.0,
    top_n: int = 20,
    data_path: str | None = None,
) -> dict:
    df = load_bond_data(data_path) if data_path else load_bond_data()
    clean = df.dropna(subset=[YIELD]).copy()

    if method == "iqr":
        q1 = clean[YIELD].quantile(0.25)
        q3 = clean[YIELD].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outliers = clean[(clean[YIELD] < lower) | (clean[YIELD] > upper)].copy()
        outliers["outlier_score"] = (outliers[YIELD] - clean[YIELD].median()).abs()
        metadata = {"method": method, "lower_bound": round(float(lower), 4), "upper_bound": round(float(upper), 4)}
    else:
        mean = clean[YIELD].mean()
        std = clean[YIELD].std(ddof=0)
        clean["outlier_score"] = 0.0 if std == 0 else ((clean[YIELD] - mean) / std).abs()
        outliers = clean[clean["outlier_score"] >= threshold].copy()
        metadata = {"method": "zscore", "threshold": threshold, "mean": round(float(mean), 4), "std": round(float(std), 4)}

    outliers = outliers.sort_values("outlier_score", ascending=False)
    records = records_from_frame(outliers, top_n)
    for record, score in zip(records, outliers["outlier_score"].head(top_n), strict=False):
        record["outlier_score"] = round(float(score), 4)

    return {
        "tool": "detect_yield_outliers",
        "outlier_count": int(len(outliers)),
        "metadata": metadata,
        "records": records,
    }


def generate_bond_report(question: str, tool_outputs: Sequence[dict]) -> dict:
    market = next((item for item in tool_outputs if item.get("tool") == "describe_market"), {})
    ranked = next((item for item in tool_outputs if item.get("tool") == "rank_bonds"), {})
    outliers = next((item for item in tool_outputs if item.get("tool") == "detect_yield_outliers"), {})
    search = next((item for item in tool_outputs if item.get("tool") == "search_bonds"), {})

    yield_summary = market.get("yield_summary", {})
    volume_summary = market.get("volume_summary", {})
    top_records = ranked.get("records", [])
    outlier_records = outliers.get("records", [])

    analysis = [
        f"样本共 {market.get('sample_count', 0)} 条债券记录，收益率均值约 {yield_summary.get('mean', 'N/A')}%。",
        f"收益率中位数约 {yield_summary.get('median', 'N/A')}%，区间约为 {yield_summary.get('min', 'N/A')}% 到 {yield_summary.get('max', 'N/A')}%。",
        f"成交量均值约 {volume_summary.get('mean', 'N/A')} 亿元，中位数约 {volume_summary.get('median', 'N/A')} 亿元。",
    ]
    if top_records:
        first = top_records[0]
        analysis.append(
            f"按 {ranked.get('rank_by')} 排序的首位样本是 {first.get(BOND_NAME)}，收益率 {first.get(YIELD)}%，成交量 {first.get(VOLUME)} 亿元。"
        )
    if search.get("match_count"):
        analysis.append(f"检索条件命中 {search.get('match_count')} 条记录，报告优先展示前 {len(search.get('records', []))} 条。")
    if outlier_records:
        analysis.append(f"异常检测发现 {outliers.get('outlier_count')} 条收益率异常样本，最高异常分数为 {outlier_records[0].get('outlier_score')}.")
    else:
        analysis.append("按当前阈值未发现显著收益率异常样本。")

    return {
        "tool": "generate_bond_report",
        "question": question,
        "tools_used": [item.get("tool") for item in tool_outputs] + ["generate_bond_report"],
        "data_evidence": {
            "market": market,
            "search": search,
            "ranking": ranked,
            "outliers": outliers,
        },
        "analysis": analysis,
        "risk_notes": [
            "收益率较高可能对应信用、流动性、久期或估值波动风险，需要结合发行人和市场环境进一步判断。",
            "成交量低的债券可能存在流动性不足，样本内排序不等同于可交易机会。",
        ],
        "limitations": [
            "本报告仅基于项目内 data/testdata.xlsx 的静态样本计算。",
            "未接入实时行情、评级、主体财务、宏观利率曲线或新闻事件。",
            "非投资建议，仅用于学习和研究。",
        ],
    }
