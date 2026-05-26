# Contributing

BondLens AI is primarily a portfolio and learning project. Contributions are welcome when they keep the project focused on explainable, evidence-grounded bond analysis.

## Development Setup

```bash
python -m pip install -r requirements-dev.txt
python app.py
```

Open:

```text
http://localhost:5000/agent
```

## Quality Checks

Run these before opening a pull request:

```bash
python -m ruff check .
python -m pytest -q
python evals/run_agent_evals.py
python evals/run_red_team_evals.py
docker build -t bondlens-ai:local .
```

## Contribution Rules

- Keep financial answers evidence-grounded and non-advisory.
- Do not add buy/sell recommendations, return guarantees, rating opinions, or risk-free claims.
- Keep tests deterministic without OpenAI, Ollama, or live internet access.
- Preserve the `undergraduate-thesis-2024` branch as the original thesis version.
- Keep the active `main` branch focused on BondLens AI.

## Pull Request Checklist

- Tests and evals pass locally.
- README updates are bilingual when user-facing behavior changes.
- No API keys, database files, snapshots, or local runtime artifacts are committed.
- New LLM behavior is covered by guardrail or red-team evals.
