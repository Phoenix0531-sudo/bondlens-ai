## Summary

Describe the change and why it is needed.

## Validation

- [ ] `python -m ruff check .`
- [ ] `python -m pytest -q`
- [ ] `python evals/run_agent_evals.py`
- [ ] `python evals/run_red_team_evals.py`
- [ ] `docker build -t bondlens-ai:local .`

## Safety Checklist

- [ ] No API keys, `.env`, database files, or runtime snapshots are committed.
- [ ] User-facing documentation is updated in English and Chinese when behavior changes.
- [ ] LLM or Agent behavior changes are covered by tests or evals.
- [ ] Output remains non-investment-advisory and evidence-grounded.
