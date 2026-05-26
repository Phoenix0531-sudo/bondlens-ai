from app import app


def test_legacy_pages_smoke():
    client = app.test_client()

    assert client.get("/").status_code == 200
    assert client.get("/query").status_code == 200
    assert client.get("/agent").status_code == 200


def test_agent_api_smoke():
    client = app.test_client()

    response = client.post("/api/agent/query", json={"question": "找出收益率最高的债券"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["agent"] == "BondLens AI"
    assert payload["plan"]["intent"] == "ranking"
    assert "rank_bonds" in payload["tools_used"]
    assert "llm_status" in payload
    assert payload["used_llm"] is False


def test_agent_api_handles_regex_special_character_search():
    client = app.test_client()

    response = client.post("/api/agent/query", json={"question": "搜索\"[\"并给出收益率分析"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["plan"]["intent"] == "bond_report"
    assert payload["data_evidence"]["search"]["match_count"] == 0
    assert "未在 data/testdata.xlsx" in payload["final_answer"]
