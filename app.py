from __future__ import annotations

import os

from flask import Flask, jsonify, redirect, render_template, request, url_for
from pydantic import ValidationError

from bond_agent import BondAnalystAgent
from bond_agent.schemas import AgentQueryRequest, ApiError, HealthResponse, api_schema_bundle


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
DATA_MODES = {"auto", "live", "static"}


@app.route("/")
def index():
    return redirect(url_for("agent_page"))


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
    data_mode, form_error = _resolve_page_data_mode(request.values.get("data_mode", os.environ.get("BOND_DATA_MODE", "auto")))
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        result = BondAnalystAgent(data_mode=data_mode).answer(question)
        view = _build_agent_view_model(result)
    return render_template("agent.html", result=result, view=view, question=question, data_mode=data_mode, form_error=form_error)


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


def _build_agent_view_model(result: dict) -> dict:
    evidence = result.get("data_evidence", {})
    market = evidence.get("market") or {}
    ranking = evidence.get("ranking") or {}
    outliers = evidence.get("outliers") or {}
    summary = market.get("yield_summary") or {}
    volume = market.get("volume_summary") or {}

    return {
        "metrics": [
            _metric("Data Source", result.get("data_source", {}).get("runtime_mode", "unknown")),
            _metric("Rows", result.get("data_source", {}).get("row_count")),
            _metric("Median Yield", summary.get("median"), "%"),
            _metric("Evidence Score", result.get("evidence_quality", {}).get("score"), "/100"),
            _metric("Final Source", result.get("final_answer_source", "unknown")),
        ],
        "yield_bars": _distribution_bars(market.get("yield_distribution") or {}),
        "ranking_records": (ranking.get("records") or [])[:5],
        "outlier_records": (outliers.get("records") or [])[:5],
        "market_summary": [
            _metric("Yield Mean", summary.get("mean"), "%"),
            _metric("Yield Range", _range_text(summary.get("min"), summary.get("max")), "%"),
            _metric("Volume Median", volume.get("median"), "bn CNY"),
        ],
    }


def _metric(label: str, value: object, suffix: str = "") -> dict:
    if value is None:
        display = "N/A"
    else:
        display = f"{value}{suffix}" if suffix and isinstance(value, int | float) else str(value)
    return {"label": label, "value": display}


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


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_RUN_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_ENV") == "development",
    )
