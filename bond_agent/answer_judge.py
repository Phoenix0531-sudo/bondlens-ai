from __future__ import annotations

from typing import Any


def judge_answer(
    *,
    llm_status: str,
    llm_guardrail: dict,
    evidence_quality: dict,
    final_answer_source: str,
) -> dict[str, Any]:
    checks = [
        _check(
            "evidence_quality",
            "证据质量",
            "Evidence quality",
            "passed" if evidence_quality.get("score", 0) >= 55 else "warning",
            f"证据评分 {evidence_quality.get('score')}/100，等级 {evidence_quality.get('level')}。",
            f"Evidence score {evidence_quality.get('score')}/100, level {evidence_quality.get('level')}.",
        )
    ]

    if llm_status != "success":
        checks.append(
            _check(
                "llm_availability",
                "LLM 可用性",
                "LLM availability",
                "not_applicable" if llm_status == "disabled" else "failed",
                _llm_status_zh(llm_status),
                _llm_status_en(llm_status),
            )
        )
        return {
            "status": "not_applicable" if llm_status == "disabled" else "safe_fallback",
            "score": 82 if llm_status == "disabled" else 70,
            "judge_type": "deterministic_answer_judge",
            "verdict_zh": "未使用 LLM 输出，最终答案来自确定性报告。" if llm_status == "disabled" else "LLM 调用失败，最终答案已安全回退。",
            "verdict_en": "No LLM output was used; the final answer came from the deterministic report."
            if llm_status == "disabled"
            else "The LLM call failed; the final answer safely fell back to the deterministic report.",
            "recommended_action": "use_deterministic_report",
            "checks": checks,
        }

    numeric_status = llm_guardrail.get("numeric_status")
    language_status = llm_guardrail.get("language_status")
    guardrail_status = llm_guardrail.get("status")
    checks.extend(
        [
            _check(
                "numeric_faithfulness",
                "数字一致性",
                "Numeric faithfulness",
                "passed" if numeric_status == "passed" else "failed",
                f"数字检查状态：{numeric_status}。",
                f"Numeric check status: {numeric_status}.",
            ),
            _check(
                "investment_language",
                "投资语言安全",
                "Investment-language safety",
                "passed" if language_status == "passed" else "failed",
                f"风险语言检查状态：{language_status}。",
                f"Risk-language check status: {language_status}.",
            ),
        ]
    )

    if guardrail_status == "passed" and final_answer_source == "llm":
        return {
            "status": "passed",
            "score": 95,
            "judge_type": "deterministic_answer_judge",
            "verdict_zh": "LLM 输出通过数字一致性和投资语言检查，可以作为最终答案。",
            "verdict_en": "The LLM output passed numeric and investment-language checks and can be used as the final answer.",
            "recommended_action": "accept_llm_answer",
            "checks": checks,
        }

    return {
        "status": "failed_guardrail",
        "score": 45,
        "judge_type": "deterministic_answer_judge",
        "verdict_zh": "LLM 输出未通过检查，最终答案已切回确定性报告。",
        "verdict_en": "The LLM output failed checks, so the final answer was switched back to the deterministic report.",
        "recommended_action": "use_deterministic_report",
        "checks": checks,
    }


def _check(
    check_id: str,
    label_zh: str,
    label_en: str,
    status: str,
    detail_zh: str,
    detail_en: str,
) -> dict[str, str]:
    return {
        "id": check_id,
        "label_zh": label_zh,
        "label_en": label_en,
        "status": status,
        "detail_zh": detail_zh,
        "detail_en": detail_en,
    }


def _llm_status_zh(status: str) -> str:
    if status == "disabled":
        return "未配置 LLM，跳过模型输出评审。"
    if status == "failed":
        return "LLM 调用失败，不能使用模型输出。"
    return f"LLM 状态：{status}。"


def _llm_status_en(status: str) -> str:
    if status == "disabled":
        return "No LLM is configured, so model-output judging was skipped."
    if status == "failed":
        return "The LLM call failed, so model output cannot be used."
    return f"LLM status: {status}."
