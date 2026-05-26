from __future__ import annotations

import json
import os

from .data_loader import resolve_bond_data
from .evidence_quality import assess_evidence_quality
from .llm_guardrail import assess_llm_faithfulness
from .planner import classify_intent
from .risk_knowledge import retrieve_risk_explanations
from .schemas import AgentResponse
from .tools import (
    compare_bond_to_market,
    describe_market,
    detect_yield_outliers,
    generate_bond_report,
    rank_bonds,
    search_bonds,
)


DISCLAIMER = "非投资建议，仅用于学习和研究。"


class BondAnalystAgent:
    name = "BondLens AI"

    def __init__(self, data_path: str | None = None, data_mode: str | None = None, live_fetcher=None) -> None:
        self.data_path = data_path
        self.data_mode = data_mode or os.environ.get("BOND_DATA_MODE", "auto")
        self.live_fetcher = live_fetcher

    def answer(self, question: str) -> dict:
        question = question.strip() or "请概览当前债券市场样本。"
        data_frame, data_source = resolve_bond_data(
            mode=self.data_mode,
            path=self.data_path or None,
            live_fetcher=self.live_fetcher,
        )
        plan = classify_intent(question, data_path=self.data_path, data_frame=data_frame)
        tool_outputs: list[dict] = []
        tool_trace: list[str] = [
            f"User question: {question}",
            f"-> data_source(mode={data_source['runtime_mode']}, source={data_source['source_id']})",
            f"-> planner(intent={plan['intent']})",
        ]

        report = None
        for tool_name in plan["requested_tools"]:
            if tool_name == "search_bonds":
                result = search_bonds(**plan["search_params"], data_frame=data_frame)
                tool_outputs.append(result)
                tool_trace.append(f"-> search_bonds({self._compact_args(plan['search_params'])})")
            elif tool_name == "compare_bond_to_market":
                search_result = self._find_tool_output(tool_outputs, "search_bonds")
                first_record = (search_result.get("records") or [None])[0] if search_result else None
                result = compare_bond_to_market(
                    bond_name=plan["search_params"].get("name"),
                    record=first_record,
                    data_frame=data_frame,
                )
                tool_outputs.append(result)
                tool_trace.append("-> compare_bond_to_market()")
            elif tool_name == "describe_market":
                result = describe_market(data_frame=data_frame)
                tool_outputs.append(result)
                tool_trace.append("-> describe_market()")
            elif tool_name == "rank_bonds":
                result = rank_bonds(
                    by=plan["rank_by"] or "yield",
                    top_n=5,
                    ascending=plan["ascending"],
                    data_frame=data_frame,
                )
                tool_outputs.append(result)
                tool_trace.append(f"-> rank_bonds(by={plan['rank_by'] or 'yield'}, top_n=5)")
            elif tool_name == "detect_yield_outliers":
                result = detect_yield_outliers(method="zscore", threshold=3.0, top_n=5, data_frame=data_frame)
                tool_outputs.append(result)
                tool_trace.append("-> detect_yield_outliers(method=zscore, threshold=3.0)")
            elif tool_name == "generate_bond_report":
                report = generate_bond_report(question, tool_outputs, plan=plan)
                tool_trace.append("-> generate_bond_report()")

        if report is None:
            report = generate_bond_report(question, tool_outputs, plan=plan)
            tool_trace.append("-> generate_bond_report()")

        risk_explanations = retrieve_risk_explanations(question, report)
        evidence_quality = assess_evidence_quality(plan, report, data_source, risk_explanations)
        report["data_source"] = data_source
        report["risk_explanations"] = risk_explanations
        report["evidence_quality"] = evidence_quality

        fallback_answer = self._format_report(report, plan)
        llm_result = self._try_llm_answer(question, plan, report)
        llm_guardrail = (
            assess_llm_faithfulness(llm_result["text"], report)
            if llm_result["status"] == "success"
            else assess_llm_faithfulness(None, report)
        )
        if llm_result["status"] == "success":
            tool_trace.append(f"-> llm_guardrail(status={llm_guardrail['status']})")

        use_llm_final = llm_result["status"] == "success" and llm_guardrail["status"] == "passed"
        final_answer = llm_result["text"] if use_llm_final else fallback_answer
        tool_trace.append("-> final answer")

        response = {
            "agent": self.name,
            "subtitle": "Explainable Bond Analysis Agent",
            "question": question,
            "plan": plan,
            "tools_used": report["tools_used"],
            "tool_trace": tool_trace,
            "data_evidence": report["data_evidence"],
            "data_source": data_source,
            "risk_explanations": risk_explanations,
            "evidence_quality": evidence_quality,
            "analysis": report["analysis"],
            "risk_notes": report["risk_notes"],
            "limitations": report["limitations"],
            "final_answer": final_answer,
            "final_answer_source": "llm" if use_llm_final else "deterministic_fallback",
            "llm_enhanced_answer": llm_result["text"],
            "llm_guardrail": llm_guardrail,
            "used_llm": llm_result["status"] == "success",
            "used_llm_in_final": use_llm_final,
            "llm_status": llm_result["status"],
            "llm_error": llm_result["error"],
            "disclaimer": DISCLAIMER,
        }
        return AgentResponse.model_validate(response).model_dump(mode="json")

    def _try_llm_answer(self, question: str, plan: dict, report: dict) -> dict:
        base_url = os.environ.get("OPENAI_BASE_URL")
        api_key = os.environ.get("OPENAI_API_KEY") or ("local-not-needed" if base_url else None)
        if not api_key:
            return {"text": None, "status": "disabled", "error": None}

        try:
            client = self._create_openai_client(api_key, base_url=base_url)
            model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
            instructions = (
                "You are a fixed-income analysis assistant. Use only the provided JSON evidence. "
                "Copy numeric evidence exactly when citing it. Do not create new percentages, ranges, "
                "ratings, issuer details, market facts, or investment advice. "
                "Do not recommend buying, selling, adding position, guaranteed returns, risk-free status, "
                "or very safe conclusions. "
                "The yield_distribution values are counts, not percentages. "
                "If the evidence is insufficient, say so directly. "
                f"Always include this disclaimer in Chinese: {DISCLAIMER}"
            )
            evidence_json = json.dumps({"question": question, "plan": plan, "report": report}, ensure_ascii=False)
            api_style = os.environ.get("OPENAI_API_STYLE", "auto").lower()
            text = self._call_llm(client, model, instructions, evidence_json, api_style, prefer_chat=bool(base_url))
            if not text:
                return {"text": None, "status": "failed", "error": "OpenAI request failed: empty_output"}
            return {"text": self._ensure_disclaimer(text.strip()), "status": "success", "error": None}
        except Exception as exc:
            return {"text": None, "status": "failed", "error": f"OpenAI request failed: {type(exc).__name__}"}

    def _create_openai_client(self, api_key: str, base_url: str | None = None):
        from openai import OpenAI

        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAI(**kwargs)

    def _call_llm(self, client, model: str, instructions: str, evidence_json: str, api_style: str, prefer_chat: bool = False) -> str | None:
        if api_style not in {"auto", "responses", "chat"}:
            raise ValueError("OPENAI_API_STYLE must be one of: auto, responses, chat")

        if api_style == "chat" or (api_style == "auto" and prefer_chat):
            return self._call_chat_completions(client, model, instructions, evidence_json)

        try:
            return self._call_responses_api(client, model, instructions, evidence_json)
        except Exception:
            if api_style == "responses":
                raise
            return self._call_chat_completions(client, model, instructions, evidence_json)

    def _call_responses_api(self, client, model: str, instructions: str, evidence_json: str) -> str | None:
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=evidence_json,
        )
        return getattr(response, "output_text", None)

    def _call_chat_completions(self, client, model: str, instructions: str, evidence_json: str) -> str | None:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": evidence_json},
            ],
        )
        choices = getattr(response, "choices", None) or []
        if not choices:
            return None
        message = getattr(choices[0], "message", None)
        return getattr(message, "content", None)

    def _ensure_disclaimer(self, text: str) -> str:
        if DISCLAIMER in text:
            return text
        return f"{text}\n\n{DISCLAIMER}"

    def _format_report(self, report: dict, plan: dict) -> str:
        evidence = report["data_evidence"]
        market = evidence.get("market") or {}
        ranking = evidence.get("ranking") or {}
        outliers = evidence.get("outliers") or {}
        comparison = evidence.get("comparison") or {}

        lines = [
            f"Question: {report['question']}",
            f"Intent: {plan['intent']}",
            "",
            "Tools Used:",
            *[f"- {tool}" for tool in report["tools_used"]],
            "",
            "Data Evidence:",
        ]

        data_source = report.get("data_source") or {}
        evidence_quality = report.get("evidence_quality") or {}
        risk_explanations = report.get("risk_explanations") or []
        if data_source:
            lines.append(f"- 数据源: {data_source.get('source_name')} ({data_source.get('runtime_mode')})")
            if data_source.get("fetched_at"):
                lines.append(f"- 获取时间: {data_source.get('fetched_at')}")
            if data_source.get("fallback_reason"):
                lines.append(f"- 实时数据降级原因: {data_source.get('fallback_reason')}")
            lines.append(f"- 样本行数: {data_source.get('row_count')}，有效收益率记录: {data_source.get('valid_yield_count')}")

        if market:
            lines.append(f"- 样本数量: {market.get('sample_count', 0)}")
            lines.append(f"- 收益率摘要: {market.get('yield_summary', {})}")
        if ranking:
            lines.append(f"- 排序字段: {ranking.get('rank_by')}")
        if outliers:
            lines.append(f"- 异常样本数量: {outliers.get('outlier_count', 0)}")
        search = evidence.get("search") or {}
        if search:
            lines.append(f"- 检索条件: {search.get('criteria', {})}")
            lines.append(f"- 检索命中数量: {search.get('match_count', 0)}")
            for index, record in enumerate(search.get("records", [])[:5], start=1):
                lines.append(
                    f"  {index}. {record.get('债券简称')} | 待偿期 {record.get('待偿期')} | "
                    f"收益率 {record.get('收盘到期收益率(%)')}% | 成交量 {record.get('交易量(亿元)')} 亿元"
                )
        if comparison:
            lines.append(
                f"- 债券相对市场: yield_percentile={comparison.get('yield_percentile')}, "
                f"volume_percentile={comparison.get('volume_percentile')}, "
                f"is_yield_outlier={comparison.get('is_yield_outlier')}"
            )

        if risk_explanations:
            lines.extend(["", "Risk Explanation Layer:"])
            for item in risk_explanations:
                lines.append(f"- {item.get('title')}: {item.get('summary')}")

        if evidence_quality:
            lines.extend(
                [
                    "",
                    "Evidence Quality:",
                    f"- Score: {evidence_quality.get('score')}/100",
                    f"- Level: {evidence_quality.get('level')}",
                    f"- Data Freshness: {evidence_quality.get('data_freshness')}",
                    f"- Decision Confidence: {evidence_quality.get('decision_confidence')}",
                    f"- Summary: {evidence_quality.get('summary')}",
                ]
            )

        lines.extend(
            [
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
        )
        return "\n".join(lines)

    def _find_tool_output(self, tool_outputs: list[dict], tool_name: str) -> dict | None:
        return next((item for item in tool_outputs if item.get("tool") == tool_name), None)

    def _compact_args(self, params: dict) -> str:
        visible = [f"{key}={value}" for key, value in params.items() if key != "limit"]
        return ", ".join(visible) if visible else "no filters"
