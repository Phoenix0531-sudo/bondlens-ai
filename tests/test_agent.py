from bond_agent import BondAnalystAgent


def test_agent_fallback_uses_local_tools_without_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = BondAnalystAgent().answer("搜索23附息国债26并给出收益率分析")

    assert result["used_llm"] is False
    assert "search_bonds" in result["tools_used"]
    assert "generate_bond_report" in result["tools_used"]
    assert "非投资建议，仅用于学习和研究" in result["final_answer"]
    assert result["tool_trace"][-1] == "-> final answer"
