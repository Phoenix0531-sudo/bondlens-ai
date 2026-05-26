from bond_agent.llm_guardrail import assess_llm_faithfulness


def _report():
    return {
        "data_evidence": {
            "market": {
                "yield_summary": {"mean": 2.77, "median": 2.45},
                "yield_distribution": {"(0.0814, 11.515]": 3089},
            }
        }
    }


def test_llm_guardrail_accepts_supported_numbers_and_safe_language():
    result = assess_llm_faithfulness("样本收益率中位数为 2.45%。非投资建议，仅用于学习和研究。", _report())

    assert result["status"] == "passed"
    assert result["numeric_status"] == "passed"
    assert result["language_status"] == "passed"
    assert result["unsupported_numbers"] == []
    assert result["unsafe_phrases"] == []


def test_llm_guardrail_rejects_unsupported_numbers():
    result = assess_llm_faithfulness("样本中 99% 的收益率都在合理范围。", _report())

    assert result["status"] == "failed"
    assert result["numeric_status"] == "failed"
    assert any(item["text"] == "99%" for item in result["unsupported_numbers"])


def test_llm_guardrail_rejects_investment_advice_language():
    result = assess_llm_faithfulness("建议买入这只债券，收益看起来非常安全。", _report())

    assert result["status"] == "failed"
    assert result["language_status"] == "failed"
    assert {item["rule_id"] for item in result["unsafe_phrases"]} == {"buy_recommendation", "risk_free_claim"}
