from evals.run_agent_evals import load_cases


def test_eval_cases_load():
    cases = load_cases()

    assert len(cases) >= 8
    assert all("expected_intent" in case for case in cases)
    assert all("expected_tools" in case for case in cases)
