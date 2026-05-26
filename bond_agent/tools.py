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


def _resolve_frame(data_frame: pd.DataFrame | None = None, data_path: str | None = None) -> pd.DataFrame:
    return data_frame.copy() if data_frame is not None else load_bond_data(data_path) if data_path else load_bond_data()


def search_bonds(
    name: str | None = None,
    min_maturity: float | None = None,
    max_maturity: float | None = None,
    min_yield: float | None = None,
    max_yield: float | None = None,
    limit: int = 20,
    data_path: str | None = None,
    data_frame: pd.DataFrame | None = None,
) -> dict:
    df = _resolve_frame(data_frame=data_frame, data_path=data_path)

    if name:
        df = df[df[BOND_NAME].str.contains(name, case=False, na=False, regex=False)]
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


def describe_market(data_path: str | None = None, data_frame: pd.DataFrame | None = None) -> dict:
    df = _resolve_frame(data_frame=data_frame, data_path=data_path)
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
    data_frame: pd.DataFrame | None = None,
) -> dict:
    df = _resolve_frame(data_frame=data_frame, data_path=data_path)
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
    data_frame: pd.DataFrame | None = None,
) -> dict:
    df = _resolve_frame(data_frame=data_frame, data_path=data_path)
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


def compare_bond_to_market(
    bond_name: str | None = None,
    record: dict | None = None,
    data_path: str | None = None,
    data_frame: pd.DataFrame | None = None,
    outlier_threshold: float = 3.0,
) -> dict:
    df = _resolve_frame(data_frame=data_frame, data_path=data_path)
    target = None

    if record:
        target_name = record.get(BOND_NAME)
        if target_name:
            matches = df[df[BOND_NAME] == target_name]
            if not matches.empty:
                target = matches.iloc[0]

    if target is None and bond_name:
        matches = df[df[BOND_NAME].str.contains(bond_name, case=False, na=False, regex=False)]
        if not matches.empty:
            target = matches.iloc[0]

    if target is None:
        return {
            "tool": "compare_bond_to_market",
            "bond_name": bond_name,
            "found": False,
            "message": "No matching bond record found in the active bond data source.",
        }

    yield_series = pd.to_numeric(df[YIELD], errors="coerce").dropna()
    volume_series = pd.to_numeric(df[VOLUME], errors="coerce").dropna()
    maturity_series = pd.to_numeric(df[MATURITY_YEARS], errors="coerce").dropna()

    target_yield = float(target[YIELD]) if pd.notna(target[YIELD]) else None
    target_volume = float(target[VOLUME]) if pd.notna(target[VOLUME]) else None
    target_maturity = float(target[MATURITY_YEARS]) if pd.notna(target[MATURITY_YEARS]) else None

    yield_mean = yield_series.mean()
    yield_std = yield_series.std(ddof=0)
    yield_zscore = None if target_yield is None or yield_std == 0 else (target_yield - yield_mean) / yield_std
    is_yield_outlier = bool(yield_zscore is not None and abs(yield_zscore) >= outlier_threshold)

    return {
        "tool": "compare_bond_to_market",
        "bond_name": target[BOND_NAME],
        "found": True,
        "record": records_from_frame(pd.DataFrame([target]), 1)[0],
        "yield_percentile": _percentile(yield_series, target_yield),
        "volume_percentile": _percentile(volume_series, target_volume),
        "maturity_percentile": _percentile(maturity_series, target_maturity),
        "yield_zscore": None if yield_zscore is None else round(float(yield_zscore), 4),
        "is_yield_outlier": is_yield_outlier,
        "nearest_market_context": _market_context(target_yield, target_volume, yield_series, volume_series),
    }


def generate_bond_report(question: str, tool_outputs: Sequence[dict], plan: dict | None = None) -> dict:
    market = next((item for item in tool_outputs if item.get("tool") == "describe_market"), {})
    ranked = next((item for item in tool_outputs if item.get("tool") == "rank_bonds"), {})
    outliers = next((item for item in tool_outputs if item.get("tool") == "detect_yield_outliers"), {})
    search = next((item for item in tool_outputs if item.get("tool") == "search_bonds"), {})
    comparison = next((item for item in tool_outputs if item.get("tool") == "compare_bond_to_market"), {})
    intent = (plan or {}).get("intent", "bond_report")

    analysis = _build_analysis(intent, market, ranked, outliers, search, comparison)

    return {
        "tool": "generate_bond_report",
        "question": question,
        "tools_used": [item.get("tool") for item in tool_outputs] + ["generate_bond_report"],
        "data_evidence": {
            "market": market,
            "search": search,
            "ranking": ranked,
            "outliers": outliers,
            "comparison": comparison,
        },
        "analysis": analysis,
        "risk_notes": [
            "收益率较高可能对应信用、流动性、久期或估值波动风险，需要结合发行人和市场环境进一步判断。",
            "成交量低的债券可能存在流动性不足，样本内排序不等同于可交易机会。",
        ],
        "limitations": [
            "本报告仅基于当前 Agent 数据源的可用字段计算。",
            "公开实时接口可能受交易时段、第三方源稳定性和字段覆盖限制影响。",
            "未接入评级、主体财务、宏观利率曲线或新闻事件。",
            "非投资建议，仅用于学习和研究。",
        ],
    }


def _percentile(series: pd.Series, value: float | None) -> float | None:
    if value is None or series.empty:
        return None
    return round(float((series <= value).mean() * 100), 2)


def _market_context(
    target_yield: float | None,
    target_volume: float | None,
    yield_series: pd.Series,
    volume_series: pd.Series,
) -> str:
    notes = []
    if target_yield is not None and not yield_series.empty:
        median_yield = yield_series.median()
        direction = "高于" if target_yield >= median_yield else "低于"
        notes.append(f"收益率{direction}样本中位数 {round(float(median_yield), 4)}%。")
    if target_volume is not None and not volume_series.empty:
        median_volume = volume_series.median()
        direction = "高于" if target_volume >= median_volume else "低于"
        notes.append(f"成交量{direction}样本中位数 {round(float(median_volume), 4)} 亿元。")
    return "".join(notes)


def _build_analysis(
    intent: str,
    market: dict,
    ranked: dict,
    outliers: dict,
    search: dict,
    comparison: dict,
) -> list[str]:
    if search.get("records"):
        record = search["records"][0]
        if search.get("criteria", {}).get("name") is None:
            preview_names = "、".join(str(item.get(BOND_NAME)) for item in search["records"][:5])
            return [
            f"检索条件命中 {search.get('match_count')} 条记录。",
            f"前 {min(5, len(search['records']))} 条样本包括：{preview_names}。",
            "该结果是筛选列表，不代表投资优先级；如需单券分析，请提供具体债券简称。",
            ]
        analysis = [
            f"检索命中 {search.get('match_count')} 条记录，优先分析 {record.get(BOND_NAME)}。",
            f"{record.get(BOND_NAME)} 的待偿期为 {_display_maturity(record)}，收盘净价 {record.get(PRICE)} 元，收益率 {record.get(YIELD)}%，成交量 {record.get(VOLUME)} 亿元。",
        ]
        if comparison.get("found"):
            analysis.append(
                f"相对全市场样本，它的收益率分位数为 {comparison.get('yield_percentile')}%，成交量分位数为 {comparison.get('volume_percentile')}%，期限分位数为 {comparison.get('maturity_percentile')}%。"
            )
            outlier_text = "属于" if comparison.get("is_yield_outlier") else "不属于"
            analysis.append(f"按 z-score 阈值判断，该债券{outlier_text}收益率异常样本。{comparison.get('nearest_market_context', '')}")
        if market:
            analysis.append(
                f"全市场背景：样本收益率中位数约 {market.get('yield_summary', {}).get('median', 'N/A')}%，均值约 {market.get('yield_summary', {}).get('mean', 'N/A')}%。"
            )
        return analysis

    if search and search.get("match_count") == 0:
        return [
            "未在当前债券数据源中找到符合条件的债券记录。",
            "请检查债券简称、收益率范围或待偿期条件；本项目不会凭空补充数据源之外的信息。",
        ]

    if intent == "ranking":
        records = ranked.get("records", [])
        if not records:
            return ["排序工具未返回可用记录。"]
        first = records[0]
        return [
            f"本次按 {ranked.get('rank_by')} 排序，返回前 {len(records)} 条样本。",
            f"排名首位为 {first.get(BOND_NAME)}，收益率 {first.get(YIELD)}%，成交量 {first.get(VOLUME)} 亿元，待偿期 {_display_maturity(first)}。",
            "排序结果只反映当前样本字段，不代表投资优先级。",
        ]

    if intent == "outlier_detection":
        records = outliers.get("records", [])
        if not records:
            return ["按当前阈值未发现显著收益率异常样本。"]
        first = records[0]
        return [
            f"异常检测使用 {outliers.get('metadata', {}).get('method')} 方法，共发现 {outliers.get('outlier_count')} 条收益率异常样本。",
            f"异常分数最高的是 {first.get(BOND_NAME)}，收益率 {first.get(YIELD)}%，异常分数 {first.get('outlier_score')}。",
            "异常收益率需要结合信用风险、流动性、估值和数据质量进一步核查。",
        ]

    yield_summary = market.get("yield_summary", {})
    volume_summary = market.get("volume_summary", {})
    analysis = [
        f"样本共 {market.get('sample_count', 0)} 条债券记录，收益率均值约 {yield_summary.get('mean', 'N/A')}%。",
        f"收益率中位数约 {yield_summary.get('median', 'N/A')}%，区间约为 {yield_summary.get('min', 'N/A')}% 到 {yield_summary.get('max', 'N/A')}%。",
        f"成交量均值约 {volume_summary.get('mean', 'N/A')} 亿元，中位数约 {volume_summary.get('median', 'N/A')} 亿元。",
    ]
    if ranked.get("records"):
        first = ranked["records"][0]
        analysis.append(
            f"按 {ranked.get('rank_by')} 排序的首位样本是 {first.get(BOND_NAME)}，收益率 {first.get(YIELD)}%，成交量 {first.get(VOLUME)} 亿元。"
        )
    if outliers.get("records"):
        analysis.append(f"异常检测发现 {outliers.get('outlier_count')} 条收益率异常样本。")
    return analysis


def _display_maturity(record: dict) -> str:
    maturity = record.get(MATURITY)
    if maturity is not None and str(maturity).strip():
        return str(maturity)
    return "当前数据源暂缺"
