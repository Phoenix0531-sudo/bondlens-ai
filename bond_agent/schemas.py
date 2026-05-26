from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DataMode = Literal["auto", "live", "static"]
LLMStatus = Literal["disabled", "success", "failed"]
GuardrailStatus = Literal["not_run", "passed", "failed"]
FinalAnswerSource = Literal["llm", "deterministic_fallback"]


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class AgentQueryRequest(BaseModel):
    question: str = Field(default="", description="Natural-language bond analysis question.")
    data_mode: str | None = Field(default=None, description="Data source mode: auto, live, or static.")


class AgentPlan(FlexibleModel):
    intent: str
    requested_tools: list[str]
    search_params: dict[str, Any] = Field(default_factory=dict)
    rank_by: str | None = None
    ascending: bool = False


class DataSourceProfile(FlexibleModel):
    source_id: str
    source_name: str
    storage: str
    runtime_mode: str
    requested_mode: str
    fetched_at: str | None = None
    fallback_reason: str | None = None
    row_count: int
    valid_yield_count: int
    columns: list[str]
    active_live_feed: bool
    active_live_snapshot: bool = False
    provider: str
    legacy_crawler: dict[str, Any] | None = None
    limitations: list[str] = Field(default_factory=list)


class RiskExplanation(BaseModel):
    id: str
    title: str
    summary: str
    watch_points: list[str]
    source: str
    retrieval_score: int


class EvidenceQuality(FlexibleModel):
    score: int
    level: Literal["low", "medium", "high"]
    analysis_confidence: str
    decision_confidence: str
    data_freshness: str
    coverage: dict[str, Any]
    checks: list[str]
    penalties: list[str]
    summary: str


class LLMGuardrail(FlexibleModel):
    status: GuardrailStatus
    numeric_status: GuardrailStatus
    language_status: GuardrailStatus
    score: int | None = None
    used_for_final: bool
    unsupported_numbers: list[dict[str, Any]] = Field(default_factory=list)
    unsafe_phrases: list[dict[str, Any]] = Field(default_factory=list)
    supported_number_count: int
    checked_number_count: int
    summary: str


class DataEvidence(FlexibleModel):
    market: dict[str, Any] = Field(default_factory=dict)
    search: dict[str, Any] = Field(default_factory=dict)
    ranking: dict[str, Any] = Field(default_factory=dict)
    outliers: dict[str, Any] = Field(default_factory=dict)
    comparison: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    agent: str
    subtitle: str
    question: str
    plan: AgentPlan
    tools_used: list[str]
    tool_trace: list[str]
    data_evidence: DataEvidence
    data_source: DataSourceProfile
    risk_explanations: list[RiskExplanation]
    evidence_quality: EvidenceQuality
    analysis: list[str]
    risk_notes: list[str]
    limitations: list[str]
    final_answer: str
    final_answer_source: FinalAnswerSource
    llm_enhanced_answer: str | None = None
    llm_guardrail: LLMGuardrail
    used_llm: bool
    used_llm_in_final: bool
    llm_status: LLMStatus
    llm_error: str | None = None
    disclaimer: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    checks: dict[str, str]


class ApiError(BaseModel):
    error: str
    allowed_data_modes: list[DataMode] | None = None
    details: list[dict[str, Any]] | None = None


def api_schema_bundle() -> dict[str, Any]:
    return {
        "agent_query_request": AgentQueryRequest.model_json_schema(),
        "agent_response": AgentResponse.model_json_schema(),
        "health_response": HealthResponse.model_json_schema(),
        "api_error": ApiError.model_json_schema(),
    }
