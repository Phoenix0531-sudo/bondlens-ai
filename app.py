from __future__ import annotations

import os

from flask import Flask, jsonify, redirect, render_template, request, url_for
from pydantic import ValidationError

from bond_agent import BondAnalystAgent
from bond_agent.schemas import AgentQueryRequest, ApiError, HealthResponse, api_schema_bundle


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
DATA_MODES = {"auto", "live", "static"}
LANGUAGES = {"zh", "en"}

INTENT_LABELS = {
    "bond_report": {"zh": "单券分析", "en": "Bond report"},
    "bond_search": {"zh": "债券筛选", "en": "Bond search"},
    "market_overview": {"zh": "市场概览", "en": "Market overview"},
    "ranking": {"zh": "排序分析", "en": "Ranking"},
    "outlier_detection": {"zh": "异常检测", "en": "Outlier detection"},
}

TOOL_LABELS = {
    "search_bonds": {"zh": "债券检索", "en": "Bond search"},
    "compare_bond_to_market": {"zh": "单券对比市场", "en": "Bond vs market"},
    "describe_market": {"zh": "市场概览", "en": "Market overview"},
    "rank_bonds": {"zh": "债券排序", "en": "Bond ranking"},
    "detect_yield_outliers": {"zh": "收益率异常检测", "en": "Yield outlier detection"},
    "generate_bond_report": {"zh": "生成分析报告", "en": "Report composition"},
}

RISK_TRANSLATIONS = {
    "yield_risk": {
        "title": "收益率是风险信号，不是投资建议",
        "summary": "较高收益率通常是在补偿信用风险、流动性风险、久期暴露或定价不确定性。",
        "watch_points": ["应与相近期限债券比较收益率。", "把高收益样本视为需要核查的信号，而不是直接机会。"],
    },
    "liquidity_risk": {
        "title": "成交量是流动性代理指标",
        "summary": "低成交量可能意味着买卖价差更宽、执行更困难；样本内看起来有吸引力的债券也可能不易交易。",
        "watch_points": ["结合市场样本比较成交量分位数。", "把低成交量排名视为流动性提醒，而不是交易机会。"],
    },
    "duration_risk": {
        "title": "更长期限会提高利率敏感性",
        "summary": "长期债券通常对利率变化更敏感；收益率比较在期限区间相近时更有意义。",
        "watch_points": ["比较收益率前先看期限分位数。", "区分短期限存单、长期国债和政策性金融债等不同类型。"],
    },
    "outlier_risk": {
        "title": "收益率异常需要结合数据与信用核查",
        "summary": "收益率异常可能来自真实风险、陈旧报价、数据质量问题或债券类型差异，应触发复核而不是直接行动。",
        "watch_points": ["先检查命中的债券记录。", "判断异常来自收益率、期限、成交量还是缺失上下文。"],
    },
    "credit_risk": {
        "title": "信用上下文不在当前行情源内",
        "summary": "当前行情源不包含主体评级、财务报表、担保或信用事件，因此信用结论必须保持克制。",
        "watch_points": ["不要只根据收益率推断评级。", "做信用判断前应补充主体、评级和事件数据。"],
    },
    "data_boundary": {
        "title": "数据覆盖范围限制决策置信度",
        "summary": "Agent 可使用 AkShare 实时债券数据和本地 Excel 备用样本；每个回答都应说明当前数据源，并避免超出字段范围的结论。",
        "watch_points": ["讨论时效性前先检查 data_source。", "做信用或投资判断前应补充主体、评级、曲线和新闻数据。"],
    },
}


@app.route("/")
def index():
    return redirect(url_for("agent_page"))


@app.context_processor
def inject_language_context():
    return {"current_lang": _resolve_language(request.values.get("lang"))}


@app.route("/healthz")
def healthz():
    response = HealthResponse(status="ok", service="BondLens AI", checks={"app": "ok"})
    return jsonify(response.model_dump(mode="json"))


@app.route("/agent", methods=["GET", "POST"])
def agent_page():
    result = None
    view = None
    question = ""
    form_error = None
    lang = _resolve_language(request.values.get("lang"))
    data_mode, form_error = _resolve_page_data_mode(request.values.get("data_mode", os.environ.get("BOND_DATA_MODE", "auto")))
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        result = BondAnalystAgent(data_mode=data_mode).answer(question)
        view = _build_agent_view_model(result, lang=lang)
    return render_template(
        "agent.html",
        result=result,
        view=view,
        question=question,
        data_mode=data_mode,
        form_error=form_error,
        lang=lang,
    )


@app.route("/api/agent/query", methods=["POST"])
def agent_query():
    payload = request.get_json(silent=True) or {}
    try:
        query = AgentQueryRequest.model_validate(payload) if payload else AgentQueryRequest(question=request.form.get("question", ""))
    except ValidationError as exc:
        return jsonify(ApiError(error="Invalid agent query request.", details=exc.errors()).model_dump(mode="json")), 400
    question = query.question or request.form.get("question", "")
    try:
        data_mode = _normalize_data_mode(query.data_mode or request.form.get("data_mode") or os.environ.get("BOND_DATA_MODE", "auto"))
    except ValueError as exc:
        error = ApiError(error=str(exc), allowed_data_modes=sorted(DATA_MODES))
        return jsonify(error.model_dump(mode="json", exclude_none=True)), 400
    result = BondAnalystAgent(data_mode=data_mode).answer(question)
    return jsonify(result)


@app.route("/api/agent/schema")
def agent_schema():
    return jsonify(api_schema_bundle())


def _normalize_data_mode(value: str | None) -> str:
    mode = (value or "auto").strip().lower()
    if mode not in DATA_MODES:
        allowed = ", ".join(sorted(DATA_MODES))
        raise ValueError(f"Unsupported data_mode: {value}. Choose from: {allowed}.")
    return mode


def _resolve_page_data_mode(value: str | None) -> tuple[str, str | None]:
    try:
        return _normalize_data_mode(value), None
    except ValueError as exc:
        return "auto", str(exc)


def _resolve_language(value: str | None) -> str:
    lang = (value or "zh").strip().lower()
    return lang if lang in LANGUAGES else "zh"


def _build_agent_view_model(result: dict, lang: str = "zh") -> dict:
    evidence = result.get("data_evidence", {})
    market = evidence.get("market") or {}
    ranking = evidence.get("ranking") or {}
    outliers = evidence.get("outliers") or {}
    summary = market.get("yield_summary") or {}
    volume = market.get("volume_summary") or {}

    return {
        "metrics": [
            _metric("Data Source", "数据源", _localized_status(result.get("data_source", {}).get("runtime_mode", "unknown"), lang), lang),
            _metric("Rows", "样本行数", result.get("data_source", {}).get("row_count"), lang),
            _metric("Median Yield", "收益率中位数", summary.get("median"), lang, "%"),
            _metric("Evidence Score", "证据评分", result.get("evidence_quality", {}).get("score"), lang, "/100"),
            _metric("Final Source", "最终来源", _localized_status(result.get("final_answer_source", "unknown"), lang), lang),
        ],
        "yield_bars": _distribution_bars(market.get("yield_distribution") or {}),
        "ranking_records": (ranking.get("records") or [])[:5],
        "outlier_records": (outliers.get("records") or [])[:5],
        "market_summary": [
            _metric("Yield Mean", "收益率均值", summary.get("mean"), lang, "%"),
            _metric("Yield Range", "收益率区间", _range_text(summary.get("min"), summary.get("max")), lang, "%"),
            _metric("Volume Median", "成交量中位数", volume.get("median"), lang, "bn CNY" if lang == "en" else " 亿元"),
        ],
        "tool_trace": [_localize_trace_item(item, lang) for item in result.get("tool_trace", [])],
        "tool_trace_by_lang": {
            "zh": [_localize_trace_item(item, "zh") for item in result.get("tool_trace", [])],
            "en": result.get("tool_trace", []),
        },
        "final_answer": _format_display_answer(result, lang),
        "final_answer_by_lang": {
            "zh": _format_display_answer(result, "zh"),
            "en": _format_display_answer(result, "en"),
        },
        "risk_explanations": [_risk_item_view(item, lang) for item in result.get("risk_explanations", [])],
        "evidence_quality_summary": _evidence_quality_summary(result.get("evidence_quality", {}), lang),
        "evidence_quality_summary_by_lang": {
            "zh": _evidence_quality_summary(result.get("evidence_quality", {}), "zh"),
            "en": result.get("evidence_quality", {}).get("summary", ""),
        },
        "llm_guardrail_summary": _llm_guardrail_summary(result.get("llm_guardrail", {}), lang),
        "llm_guardrail_summary_by_lang": {
            "zh": _llm_guardrail_summary(result.get("llm_guardrail", {}), "zh"),
            "en": result.get("llm_guardrail", {}).get("summary", ""),
        },
        "intent_label": _intent_label(result.get("plan", {}).get("intent"), lang),
        "llm_status_label": _localized_status(result.get("llm_status"), lang),
        "guardrail_status_label": _localized_status(result.get("llm_guardrail", {}).get("status"), lang),
        "evidence_level_label": _localized_status(result.get("evidence_quality", {}).get("level"), lang),
        "data_source_subtitle": _data_source_subtitle(result.get("data_source", {}), lang),
    }


def _metric(label_en: str, label_zh: str, value: object, lang: str, suffix: str = "") -> dict:
    if value is None:
        display = "N/A"
    else:
        display = f"{value}{suffix}" if suffix and isinstance(value, int | float) else str(value)
    return {
        "label": label_zh if lang == "zh" else label_en,
        "label_zh": label_zh,
        "label_en": label_en,
        "value": display,
    }


def _range_text(low: object, high: object) -> str:
    if low is None or high is None:
        return "N/A"
    return f"{low} - {high}"


def _distribution_bars(distribution: dict) -> list[dict]:
    max_count = max(distribution.values(), default=0)
    bars = []
    for label, count in distribution.items():
        width = 0 if max_count == 0 else round(float(count) / max_count * 100, 2)
        bars.append({"label": label, "count": count, "width": width})
    return bars


def _format_display_answer(result: dict, lang: str) -> str:
    if lang == "en":
        return result.get("final_answer", "")

    evidence = result.get("data_evidence", {})
    market = evidence.get("market") or {}
    ranking = evidence.get("ranking") or {}
    outliers = evidence.get("outliers") or {}
    comparison = evidence.get("comparison") or {}
    search = evidence.get("search") or {}
    data_source = result.get("data_source") or {}
    plan = result.get("plan") or {}
    evidence_quality = result.get("evidence_quality") or {}

    lines = [
        f"问题：{result.get('question')}",
        f"意图：{_intent_label(plan.get('intent'), 'zh')}（{plan.get('intent')}）",
        "",
        "使用工具：",
        *[f"- {_tool_label(tool, 'zh')}（{tool}）" for tool in result.get("tools_used", [])],
        "",
        "数据证据：",
    ]

    if data_source:
        lines.append(
            f"- 数据源：{data_source.get('source_name')}（{_localized_status(data_source.get('runtime_mode'), 'zh')}）"
        )
        if data_source.get("fetched_at"):
            lines.append(f"- 获取时间：{data_source.get('fetched_at')}")
        if data_source.get("fallback_reason"):
            lines.append(f"- 实时数据降级原因：{data_source.get('fallback_reason')}")
        lines.append(f"- 样本行数：{data_source.get('row_count')}，有效收益率记录：{data_source.get('valid_yield_count')}")

    if market:
        lines.append(f"- 样本数量：{market.get('sample_count', 0)}")
        lines.append(f"- 收益率摘要：{market.get('yield_summary', {})}")
    if ranking:
        lines.append(f"- 排序字段：{ranking.get('rank_by')}")
    if outliers:
        lines.append(f"- 异常样本数量：{outliers.get('outlier_count', 0)}")
    if search:
        lines.append(f"- 检索条件：{search.get('criteria', {})}")
        lines.append(f"- 检索命中数量：{search.get('match_count', 0)}")
        for index, record in enumerate(search.get("records", [])[:5], start=1):
            lines.append(
                f"  {index}. {record.get('债券简称')} | 待偿期 {record.get('待偿期')} | "
                f"收益率 {record.get('收盘到期收益率(%)')}% | 成交量 {record.get('交易量(亿元)')} 亿元"
            )
    if comparison:
        lines.append(
            f"- 债券相对市场：收益率分位数={comparison.get('yield_percentile')}，"
            f"成交量分位数={comparison.get('volume_percentile')}，"
            f"是否收益率异常={comparison.get('is_yield_outlier')}"
        )

    if result.get("risk_explanations"):
        lines.extend(["", "风险解释层："])
        for item in result["risk_explanations"]:
            localized = _localize_risk_item(item, "zh")
            lines.append(f"- {localized['title']}：{localized['summary']}")

    if evidence_quality:
        lines.extend(
            [
                "",
                "证据质量：",
                f"- 评分：{evidence_quality.get('score')}/100",
                f"- 等级：{_localized_status(evidence_quality.get('level'), 'zh')}",
                f"- 数据新鲜度：{_localized_status(evidence_quality.get('data_freshness'), 'zh')}",
                f"- 决策置信度：{_localized_status(evidence_quality.get('decision_confidence'), 'zh')}",
                f"- 摘要：{_evidence_quality_summary(evidence_quality, 'zh')}",
            ]
        )

    lines.extend(
        [
            "",
            "分析结论：",
            *[f"- {item}" for item in result.get("analysis", [])],
            "",
            "风险提示：",
            *[f"- {item}" for item in result.get("risk_notes", [])],
            "",
            "局限性：",
            *[f"- {item}" for item in result.get("limitations", [])],
        ]
    )
    return "\n".join(lines)


def _localize_trace_item(item: str, lang: str) -> str:
    if lang == "en":
        return item
    if item.startswith("User question:"):
        return item.replace("User question:", "用户问题：", 1)
    if item == "-> final answer":
        return "-> 最终回答"
    replacements = {
        "-> data_source": "-> 数据源",
        "-> planner": "-> 规划器",
        "intent=": "意图=",
        "mode=": "模式=",
        "source=": "来源=",
    }
    localized = item
    for source, target in replacements.items():
        localized = localized.replace(source, target)
    return localized


def _localize_risk_item(item: dict, lang: str) -> dict:
    if lang == "en":
        return {
            "title": item.get("title", ""),
            "summary": item.get("summary", ""),
            "watch_points": item.get("watch_points", []),
        }
    translation = RISK_TRANSLATIONS.get(item.get("id"), {})
    return {
        "title": translation.get("title", item.get("title", "")),
        "summary": translation.get("summary", item.get("summary", "")),
        "watch_points": translation.get("watch_points", item.get("watch_points", [])),
    }


def _risk_item_view(item: dict, lang: str) -> dict:
    zh = _localize_risk_item(item, "zh")
    en = _localize_risk_item(item, "en")
    active = zh if lang == "zh" else en
    return {
        "title": active["title"],
        "summary": active["summary"],
        "watch_points": active["watch_points"],
        "title_zh": zh["title"],
        "title_en": en["title"],
        "summary_zh": zh["summary"],
        "summary_en": en["summary"],
        "watch_points_zh": zh["watch_points"],
        "watch_points_en": en["watch_points"],
    }


def _intent_label(intent: str | None, lang: str) -> str:
    return INTENT_LABELS.get(intent or "", {}).get(lang, intent or "unknown")


def _tool_label(tool: str, lang: str) -> str:
    return TOOL_LABELS.get(tool, {}).get(lang, tool)


def _localized_status(value: object, lang: str) -> str:
    if value is None:
        return "N/A"
    if lang == "en":
        return str(value)
    mapping = {
        "live": "实时行情",
        "live_snapshot": "实时快照",
        "static_sample": "本地样本",
        "static_fallback": "本地兜底",
        "deterministic_fallback": "规则兜底",
        "success": "成功",
        "failed": "失败",
        "disabled": "未启用",
        "passed": "通过",
        "not_run": "未运行",
        "high": "高",
        "medium": "中",
        "low": "低",
        "live_fetch": "实时获取",
        "cached_live_snapshot": "缓存快照",
        "static_snapshot": "静态快照",
    }
    return mapping.get(str(value), str(value))


def _evidence_quality_summary(evidence_quality: dict, lang: str) -> str:
    if lang == "en":
        return evidence_quality.get("summary", "")
    level = _localized_status(evidence_quality.get("level"), "zh")
    return f"当前数据源的证据质量为{level}，但因为尚未接入主体信用、宏观曲线和完整证券主数据，决策置信度仍保持为低。"


def _llm_guardrail_summary(guardrail: dict, lang: str) -> str:
    if lang == "en":
        return guardrail.get("summary", "")
    status = guardrail.get("status")
    if status == "not_run":
        return "未调用 LLM 输出，因此没有运行数值一致性和投资建议语言检查。"
    if status == "passed":
        return "LLM 输出已通过数值一致性和风险语言检查。"
    return "LLM 输出未通过可信度检查，页面使用规则兜底报告作为最终答案。"


def _data_source_subtitle(data_source: dict, lang: str) -> str:
    if lang == "en":
        return f"{data_source.get('source_name')} · {data_source.get('runtime_mode')} · {data_source.get('row_count')} rows"
    return (
        f"{data_source.get('source_name')} · "
        f"{_localized_status(data_source.get('runtime_mode'), 'zh')} · "
        f"{data_source.get('row_count')} 行"
    )


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_RUN_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_ENV") == "development",
    )
