from __future__ import annotations

import json
import os
import re

from .data_loader import BOND_NAME, VOLUME, YIELD, load_bond_data
from .tools import describe_market, detect_yield_outliers, generate_bond_report, rank_bonds, search_bonds


DISCLAIMER = "非投资建议，仅用于学习和研究。"


class BondAnalystAgent:
    name = "Bond Analyst Agent"

    def __init__(self, data_path: str | None = None) -> None:
        self.data_path = data_path

    def answer(self, question: str) -> dict:
        question = question.strip() or "请概览当前债券市场样本。"
        tool_outputs: list[dict] = []
        tool_trace: list[str] = [f"User question: {question}"]

        search_params = self._extract_search_params(question)
        if search_params:
            search_result = search_bonds(**search_params, data_path=self.data_path)
            tool_outputs.append(search_result)
            tool_trace.append(f"-> search_bonds({self._compact_args(search_params)})")

        market_result = describe_market(data_path=self.data_path)
        tool_outputs.append(market_result)
        tool_trace.append("-> describe_market()")

        rank_key, ascending = self._choose_rank(question)
        ranking_result = rank_bonds(by=rank_key, top_n=5, ascending=ascending, data_path=self.data_path)
        tool_outputs.append(ranking_result)
        tool_trace.append(f"-> rank_bonds(by={rank_key}, top_n=5)")

        outlier_result = detect_yield_outliers(method="zscore", threshold=3.0, top_n=5, data_path=self.data_path)
        tool_outputs.append(outlier_result)
        tool_trace.append("-> detect_yield_outliers(method=zscore, threshold=3.0)")

        report = generate_bond_report(question, tool_outputs)
        tool_trace.append("-> generate_bond_report()")
        tool_trace.append("-> final answer")

        fallback_answer = self._format_report(report)
        llm_answer = self._try_llm_answer(question, report)
        final_answer = llm_answer or fallback_answer

        return {
            "agent": self.name,
            "question": question,
            "tools_used": report["tools_used"],
            "tool_trace": tool_trace,
            "data_evidence": report["data_evidence"],
            "analysis": report["analysis"],
            "risk_notes": report["risk_notes"],
            "limitations": report["limitations"],
            "final_answer": final_answer,
            "used_llm": bool(llm_answer),
            "disclaimer": DISCLAIMER,
        }

    def _extract_search_params(self, question: str) -> dict | None:
        params: dict = {"limit": 10}

        quoted = re.search(r"[“\"']([^“\"']+)[”\"']", question)
        if quoted:
            params["name"] = quoted.group(1).strip()
        else:
            bond_name = self._find_bond_name(question)
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

        return params if len(params) > 1 else None

    def _choose_rank(self, question: str) -> tuple[str, bool]:
        if any(word in question for word in ["成交量", "交易量", "活跃"]):
            return "volume", False
        if any(word in question for word in ["期限", "待偿期", "久期"]):
            return "maturity", False
        if any(word in question for word in ["低收益", "最低", "较低"]):
            return "yield", True
        return "yield", False

    def _find_bond_name(self, question: str) -> str | None:
        try:
            df = load_bond_data(self.data_path) if self.data_path else load_bond_data()
            names = df[BOND_NAME].dropna().astype(str).unique()
        except Exception:
            names = []

        for name in sorted(names, key=len, reverse=True):
            if name and name in question:
                return name

        bond_like = re.search(r"(\d{2}[A-Za-z0-9]+(?:CD\d+)?)", question)
        return bond_like.group(1).strip() if bond_like else None

    def _try_llm_answer(self, question: str, report: dict) -> str | None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return None

        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
            response = client.responses.create(
                model=model,
                instructions=(
                    "You are a fixed-income analysis assistant. Use only the provided JSON evidence. "
                    "Do not invent market facts, ratings, issuer details, or investment advice. "
                    f"Always include this disclaimer in Chinese: {DISCLAIMER}"
                ),
                input=json.dumps({"question": question, "report": report}, ensure_ascii=False),
            )
            text = getattr(response, "output_text", None)
            return text.strip() if text else None
        except Exception:
            return None

    def _format_report(self, report: dict) -> str:
        lines = [
            f"Question: {report['question']}",
            "",
            "Tools Used:",
            *[f"- {tool}" for tool in report["tools_used"]],
            "",
            "Data Evidence:",
            f"- 样本数量: {report['data_evidence']['market'].get('sample_count', 0)}",
            f"- 收益率摘要: {report['data_evidence']['market'].get('yield_summary', {})}",
            f"- 排序字段: {report['data_evidence']['ranking'].get('rank_by')}",
            f"- 异常样本数量: {report['data_evidence']['outliers'].get('outlier_count', 0)}",
            "",
            "Analysis:",
            *[f"- {item}" for item in report["analysis"]],
            "",
            "Risk Notes:",
            *[f"- {item}" for item in report["risk_notes"]],
            "",
            "Limitations:",
            *[f"- {item}" for item in report["limitations"]],
        ]
        return "\n".join(lines)

    def _compact_args(self, params: dict) -> str:
        return ", ".join(f"{key}={value}" for key, value in params.items() if key != "limit")
