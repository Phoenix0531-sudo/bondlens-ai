from bond_agent.replay_store import list_replays, save_replay


def test_replay_store_saves_sanitized_summary(monkeypatch, tmp_path):
    monkeypatch.setenv("BOND_REPLAY_DIR", str(tmp_path))

    record = save_replay(
        {
            "question": "当前样本收益率分布是什么样？",
            "plan": {"intent": "market_overview"},
            "tools_used": ["describe_market", "generate_bond_report"],
            "data_source": {
                "source_id": "local_static_excel",
                "source_name": "data/testdata.xlsx",
                "runtime_mode": "static_sample",
                "row_count": 3000,
                "valid_yield_count": 2900,
            },
            "evidence_quality": {
                "score": 70,
                "level": "medium",
                "data_freshness": "static_snapshot",
                "decision_confidence": "low",
            },
            "llm_guardrail": {"status": "not_run"},
            "answer_judge": {"status": "not_applicable"},
            "risk_profile": {"overall_level": "medium", "summary_zh": "中文摘要", "summary_en": "English summary"},
            "llm_status": "disabled",
            "final_answer_source": "deterministic_fallback",
            "evidence_ledger": [{"id": "data_source"}],
        }
    )

    assert record is not None
    records = list_replays()
    assert len(records) == 1
    assert records[0]["question"] == "当前样本收益率分布是什么样？"
    assert records[0]["data_source"]["runtime_mode"] == "static_sample"
    assert "final_answer" not in records[0]
