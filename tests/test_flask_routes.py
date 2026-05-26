from app import app


def test_agent_pages_smoke():
    client = app.test_client()

    assert client.get("/").status_code == 302
    response = client.get("/agent?data_mode=static")

    assert response.status_code == 200
    assert b"Agent Console" in response.data
    assert b"Evidence Console" not in response.data


def test_agent_page_exposes_language_switch():
    client = app.test_client()

    response = client.get("/agent?data_mode=static&lang=zh")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-language-option="zh"' in html
    assert 'data-language-option="en"' in html
    assert "智能体控制台" in html
    assert "Agent Console" in html


def test_agent_page_localizes_result_for_chinese():
    client = app.test_client()

    response = client.post(
        "/agent",
        data={"question": "当前样本收益率分布是什么样？", "data_mode": "static", "lang": "zh"},
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "最终回答" in html
    assert "问题：" in html
    assert "风险解释层" in html
    assert "工具轨迹" in html
    assert "跳过：LLM 未启用" in html


def test_healthz():
    client = app.test_client()

    response = client.get("/healthz")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {"checks": {"app": "ok"}, "service": "BondLens AI", "status": "ok"}


def test_agent_schema_endpoint():
    client = app.test_client()

    response = client.get("/api/agent/schema")

    assert response.status_code == 200
    payload = response.get_json()
    assert "agent_query_request" in payload
    assert "agent_response" in payload
    assert "api_error" in payload
    assert "final_answer" in payload["agent_response"]["properties"]
    assert "llm_guardrail" in payload["agent_response"]["properties"]


def test_agent_api_smoke():
    client = app.test_client()

    response = client.post("/api/agent/query", json={"question": "找出收益率最高的债券", "data_mode": "static"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["agent"] == "BondLens AI"
    assert payload["plan"]["intent"] == "ranking"
    assert "rank_bonds" in payload["tools_used"]
    assert "llm_status" in payload
    assert payload["data_source"]["runtime_mode"] == "static_sample"
    assert payload["risk_explanations"]
    assert payload["evidence_quality"]["decision_confidence"] == "low"
    assert payload["used_llm"] is False


def test_agent_api_rejects_invalid_data_mode():
    client = app.test_client()

    response = client.post("/api/agent/query", json={"question": "test", "data_mode": "bad"})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["allowed_data_modes"] == ["auto", "live", "static"]
    assert "Unsupported data_mode" in payload["error"]


def test_agent_api_handles_regex_special_character_search():
    client = app.test_client()

    response = client.post("/api/agent/query", json={"question": "搜索\"[\"并给出收益率分析", "data_mode": "static"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["plan"]["intent"] == "bond_report"
    assert payload["data_evidence"]["search"]["match_count"] == 0
    assert "未在当前债券数据源中找到符合条件的债券记录" in payload["final_answer"]
