# Modern AI Bond Agent Upgrade Todo

## Plan

- [x] Preserve original thesis state with `legacy-thesis-2024` branch and `thesis-submission-2024-04-24` tag.
- [x] Create and switch to `modern-ai-bond-agent` for all upgrade work.
- [x] Fix Flask startup issues, missing imports, secret key handling, dependencies, and minimal SQLite initialization.
- [x] Extract bond data loading and local analysis tools into `bond_agent/`.
- [x] Add a single Bond Analyst Agent with tool trace and deterministic fallback output.
- [x] Add Web/API entry points for the agent without rewriting the legacy UI.
- [x] Add focused tests for data loading, tools, fallback agent output, and Flask smoke routes.
- [x] Add Docker support, `.env.example`, and professional README documentation.
- [x] Verify local startup, tests, Docker build, and Docker-served app access.

## Review

- `python -m pytest -q`: passed, 10 tests.
- `python app.py` with `PORT=5055`: `/agent` returned HTTP 200.
- `docker compose config`: passed.
- `docker compose build`: passed.
- `docker compose up -d`: `/agent` returned HTTP 200.
- Docker API smoke test: `/api/agent/query` returned HTTP 200 with local tool trace.

# Agent Quality Pass Todo

## Branch

- [x] Start from `modern-ai-bond-agent`.
- [x] Create local working branch `agent-quality-pass`.
- [x] Do not push automatically; show summary, tests, Docker results, and suggested commits first.

## Plan

- [x] Rename product-facing project text to `BondLens AI` with subtitle `Explainable Bond Analysis Agent`.
- [x] Add `bond_agent/planner.py` with rule-based intent classification and requested tool selection.
- [x] Route actual Agent tool calls from the planner and include `plan` in API/Web responses.
- [x] Improve report generation so concrete bond searches focus on matched bonds first.
- [x] Add `compare_bond_to_market` evidence for yield, volume, maturity percentiles, and outlier status.
- [x] Add Agent Eval cases and a local runner that does not call OpenAI.
- [x] Make LLM fallback state observable with `llm_status` and safe `llm_error`.
- [x] Replace Docker dev server with gunicorn and add compose healthcheck.
- [x] Remove modern-branch-only project artifacts after confirming no app/template references.
- [x] Update README for portfolio positioning, planner/tools/evidence/report, evals, Docker, and interview talking points.

## Validation Standards

- [x] `python -m pytest -q` passes.
- [x] `python evals/run_agent_evals.py` passes.
- [x] `python app.py` serves `/agent` with HTTP 200.
- [x] `docker compose build` passes.
- [x] `docker compose up -d` serves `/agent` and `/api/agent/query` with HTTP 200.
- [x] `docker compose down` leaves no running project container.

## Review

- `python -m pytest -q --basetemp .tmp/pytest`: passed, 23 tests.
- `python evals/run_agent_evals.py`: passed, 10/10 cases.
- `python app.py` with `PORT=5055`: `/agent` returned HTTP 200.
- `docker compose build`: passed.
- `docker compose up -d`: `/agent` and `/api/agent/query` returned HTTP 200; container reported healthy.
- `docker compose down`: completed.
