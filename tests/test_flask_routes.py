from app import app


def test_agent_pages_smoke():
    client = app.test_client()

    assert client.get("/").status_code == 302
    response = client.get("/agent?data_mode=static")

    assert response.status_code == 200
    assert b"Agent Console" in response.data
    assert b"Evidence Console" not in response.data


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
