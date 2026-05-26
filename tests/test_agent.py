import pandas as pd

from bond_agent import BondAnalystAgent


def test_agent_fallback_uses_local_tools_without_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = BondAnalystAgent(data_mode="static").answer("搜索23附息国债26并给出收益率分析")

    assert result["used_llm"] is False
    assert result["llm_status"] == "disabled"
    assert result["llm_error"] is None
    assert result["plan"]["intent"] == "bond_report"
    assert result["data_source"]["source_id"] == "local_static_excel"
    assert result["data_source"]["active_live_feed"] is False
    assert result["risk_explanations"]
    assert result["evidence_quality"]["level"] in {"medium", "high"}
    assert result["evidence_quality"]["decision_confidence"] == "low"
    assert "search_bonds" in result["tools_used"]
    assert "compare_bond_to_market" in result["tools_used"]
    assert "generate_bond_report" in result["tools_used"]
    assert "23附息国债26" in result["final_answer"]
    assert "Risk Explanation Layer" in result["final_answer"]
    assert "Evidence Quality" in result["final_answer"]
    assert "非投资建议，仅用于学习和研究" in result["final_answer"]
    assert result["tool_trace"][-1] == "-> final answer"


def test_agent_tool_selection_for_market_overview(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = BondAnalystAgent(data_mode="static").answer("当前样本收益率分布是什么样？")

    assert result["plan"]["intent"] == "market_overview"
    assert result["tools_used"] == ["describe_market", "generate_bond_report"]
    assert "rank_bonds" not in result["tools_used"]
    assert "detect_yield_outliers" not in result["tools_used"]
    assert "-> generate_bond_report()" in result["tool_trace"]


def test_agent_search_only_answer_shows_search_evidence(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = BondAnalystAgent(data_mode="static").answer("筛选收益率大于 3 的债券")

    assert result["plan"]["intent"] == "bond_search"
    assert result["tools_used"] == ["search_bonds", "generate_bond_report"]
    assert "检索命中数量" in result["final_answer"]
    assert "检索条件" in result["final_answer"]


def test_agent_exposes_confidence_and_risk_retrieval(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = BondAnalystAgent(data_mode="static").answer("有没有收益率异常的债券？")

    assert result["evidence_quality"]["coverage"]["has_risk_explanations"] is True
    assert result["evidence_quality"]["data_freshness"] == "static_snapshot"
    assert any(item["id"] == "outlier_risk" for item in result["risk_explanations"])
    assert "Issuer ratings" in result["evidence_quality"]["penalties"][-1]


class _FakeResponse:
    output_text = "LLM enhanced answer。非投资建议，仅用于学习和研究。"


class _FakeResponses:
    def create(self, **kwargs):
        return _FakeResponse()


class _FakeClient:
    responses = _FakeResponses()


class _FailingResponses:
    def create(self, **kwargs):
        raise RuntimeError("boom")


class _FailingClient:
    responses = _FailingResponses()


class _FakeChatMessage:
    content = "Local LLM chat answer。"


class _FakeChatChoice:
    message = _FakeChatMessage()


class _FakeChatCompletion:
    choices = [_FakeChatChoice()]


class _FakeChatCompletions:
    def create(self, **kwargs):
        return _FakeChatCompletion()


class _FakeChat:
    completions = _FakeChatCompletions()


class _FakeLocalClient:
    chat = _FakeChat()


def test_agent_llm_status_success(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(BondAnalystAgent, "_create_openai_client", lambda self, api_key, **kwargs: _FakeClient())

    result = BondAnalystAgent(data_mode="static").answer("当前样本收益率分布是什么样？")

    assert result["used_llm"] is True
    assert result["llm_status"] == "success"
    assert result["llm_error"] is None
    assert result["final_answer"].startswith("LLM enhanced answer")


def test_agent_llm_status_failed_keeps_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_STYLE", "responses")
    monkeypatch.setattr(BondAnalystAgent, "_create_openai_client", lambda self, api_key, **kwargs: _FailingClient())

    result = BondAnalystAgent(data_mode="static").answer("当前样本收益率分布是什么样？")

    assert result["used_llm"] is False
    assert result["llm_status"] == "failed"
    assert result["llm_error"] == "OpenAI request failed: RuntimeError"
    assert "Question:" in result["final_answer"]


def test_agent_local_openai_compatible_base_url_uses_chat_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("OPENAI_MODEL", "qwen2.5:1.5b")

    seen = {}

    def fake_create_client(self, api_key, **kwargs):
        seen["api_key"] = api_key
        seen["base_url"] = kwargs.get("base_url")
        return _FakeLocalClient()

    monkeypatch.setattr(BondAnalystAgent, "_create_openai_client", fake_create_client)

    result = BondAnalystAgent(data_mode="static").answer("当前样本收益率分布是什么样？")

    assert seen["api_key"] == "local-not-needed"
    assert seen["base_url"] == "http://127.0.0.1:11434/v1"
    assert result["used_llm"] is True
    assert result["llm_status"] == "success"
    assert result["final_answer"].startswith("Local LLM chat answer")
    assert "非投资建议，仅用于学习和研究" in result["final_answer"]


def test_agent_can_use_live_bond_feed_without_openai(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def fake_fetcher():
        return pd.DataFrame(
            {
                "债券简称": ["25国开20", "26超长特别国债02", "25四川港投MTN002"],
                "成交净价": [101.23, 98.76, 100.01],
                "最新收益率": [2.12, 2.65, 3.2],
                "涨跌": [-0.3, 1.2, 0.0],
                "加权收益率": [2.11, 2.66, 3.18],
                "交易量": [4.5, 8.0, 2.1],
            }
        )

    result = BondAnalystAgent(data_mode="live", live_fetcher=fake_fetcher).answer("搜索25国开20并给出收益率分析")

    assert result["data_source"]["source_id"] == "akshare_bond_spot_deal"
    assert result["data_source"]["runtime_mode"] == "live"
    assert result["data_source"]["active_live_feed"] is True
    assert result["evidence_quality"]["data_freshness"] == "live_fetch"
    assert "25国开20" in result["final_answer"]
