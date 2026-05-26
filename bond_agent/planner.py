from __future__ import annotations

import re

from .data_loader import BOND_NAME, load_bond_data


RANK_KEYWORDS = {
    "volume": ["成交量", "交易量", "活跃"],
    "maturity": ["期限", "待偿期", "久期", "最长"],
    "price": ["净价", "价格"],
    "yield": ["收益率", "最高", "高收益", "最低", "低收益"],
}


def classify_intent(question: str, data_path: str | None = None) -> dict:
    normalized = (question or "").strip()
    search_params = _extract_search_params(normalized, data_path=data_path)
    rank_by, ascending = _choose_rank(normalized)

    if not normalized:
        return {
            "intent": "market_overview",
            "requested_tools": ["describe_market"],
            "rank_by": None,
            "ascending": False,
            "search_params": {},
            "explanation": "Empty question falls back to a market overview.",
        }

    if _is_outlier_question(normalized):
        return {
            "intent": "outlier_detection",
            "requested_tools": ["detect_yield_outliers"],
            "rank_by": None,
            "ascending": False,
            "search_params": search_params,
            "explanation": "Question asks about abnormal yield observations.",
        }

    if _is_ranking_question(normalized):
        return {
            "intent": "ranking",
            "requested_tools": ["rank_bonds"],
            "rank_by": rank_by or "yield",
            "ascending": ascending,
            "search_params": search_params,
            "explanation": f"Question asks for sorted bonds by {rank_by or 'yield'}.",
        }

    if search_params and _needs_report(normalized):
        return {
            "intent": "bond_report",
            "requested_tools": [
                "search_bonds",
                "compare_bond_to_market",
                "describe_market",
                "rank_bonds",
                "detect_yield_outliers",
                "generate_bond_report",
            ],
            "rank_by": rank_by or "yield",
            "ascending": ascending,
            "search_params": search_params,
            "explanation": "Question names or filters bonds and asks for analysis, so a full evidence report is needed.",
        }

    if search_params:
        return {
            "intent": "bond_search",
            "requested_tools": ["search_bonds"],
            "rank_by": None,
            "ascending": False,
            "search_params": search_params,
            "explanation": "Question asks to find bonds matching explicit search criteria.",
        }

    if _is_market_overview_question(normalized):
        return {
            "intent": "market_overview",
            "requested_tools": ["describe_market"],
            "rank_by": None,
            "ascending": False,
            "search_params": {},
            "explanation": "Question asks for aggregate market sample statistics.",
        }

    return {
        "intent": "bond_report",
        "requested_tools": ["describe_market", "rank_bonds", "detect_yield_outliers", "generate_bond_report"],
        "rank_by": rank_by or "yield",
        "ascending": ascending,
        "search_params": search_params,
        "explanation": "General analysis question uses a compact market report plan.",
    }


def _extract_search_params(question: str, data_path: str | None = None) -> dict:
    params: dict = {"limit": 10}

    quoted = re.search(r"[“\"']([^“\"']+)[”\"']", question)
    if quoted:
        params["name"] = quoted.group(1).strip()
    else:
        bond_name = _find_bond_name(question, data_path=data_path)
        if bond_name:
            params["name"] = bond_name

    yield_range = re.search(r"收益率.*?([0-9]+(?:\.[0-9]+)?)\s*[-到至~]\s*([0-9]+(?:\.[0-9]+)?)", question)
    if yield_range:
        params["min_yield"] = float(yield_range.group(1))
        params["max_yield"] = float(yield_range.group(2))

    min_yield = re.search(r"收益率.*?(?:大于|高于|超过|>=)\s*([0-9]+(?:\.[0-9]+)?)", question)
    if min_yield:
        params["min_yield"] = float(min_yield.group(1))

    max_yield = re.search(r"收益率.*?(?:小于|低于|不超过|<=)\s*([0-9]+(?:\.[0-9]+)?)", question)
    if max_yield:
        params["max_yield"] = float(max_yield.group(1))

    maturity_range = re.search(r"(?:期限|待偿期).*?([0-9]+(?:\.[0-9]+)?)\s*[-到至~]\s*([0-9]+(?:\.[0-9]+)?)", question)
    if maturity_range:
        params["min_maturity"] = float(maturity_range.group(1))
        params["max_maturity"] = float(maturity_range.group(2))

    return params if len(params) > 1 else {}


def _choose_rank(question: str) -> tuple[str | None, bool]:
    for rank_by, keywords in RANK_KEYWORDS.items():
        if any(keyword in question for keyword in keywords):
            ascending = rank_by == "yield" and any(word in question for word in ["低收益", "最低", "较低"])
            return rank_by, ascending
    return None, False


def _find_bond_name(question: str, data_path: str | None = None) -> str | None:
    try:
        df = load_bond_data(data_path) if data_path else load_bond_data()
        names = df[BOND_NAME].dropna().astype(str).unique()
    except Exception:
        names = []

    for name in sorted(names, key=len, reverse=True):
        if name and name in question:
            return name

    bond_like = re.search(r"(\d{2}[A-Za-z0-9]+(?:CD\d+)?)", question)
    return bond_like.group(1).strip() if bond_like else None


def _is_outlier_question(question: str) -> bool:
    return any(word in question for word in ["异常", "离群", "极端", "outlier"])


def _is_ranking_question(question: str) -> bool:
    if any(word in question for word in ["排序", "排名", "最高", "最低", "最活跃", "最长"]):
        return True
    return bool(re.search(r"(?:前|Top|top)\s*\d+", question))


def _is_market_overview_question(question: str) -> bool:
    return any(word in question for word in ["概览", "整体", "市场", "分布", "摘要", "样本", "统计"])


def _needs_report(question: str) -> bool:
    return any(word in question for word in ["分析", "报告", "说明", "解释", "怎么看", "评价"])
