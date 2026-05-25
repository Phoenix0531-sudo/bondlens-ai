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
    assert payload["agent"] == "Bond Analyst Agent"
    assert "rank_bonds" in payload["tools_used"]
    assert payload["used_llm"] is False
