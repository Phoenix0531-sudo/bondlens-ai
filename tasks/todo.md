# Modern AI Bond Agent Upgrade Todo

## Plan

- [x] Preserve original thesis state with the `undergraduate-thesis-2024` branch.
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

# Data Source, Risk RAG, Evidence Quality Todo

## Plan

- [x] Confirm current Agent data source and legacy crawler status.
- [x] Add explicit data source metadata to Agent/API responses.
- [x] Add local retrieval-augmented risk explanation layer for fixed-income concepts.
- [x] Add evidence quality and confidence assessment for every answer.
- [x] Surface data source, risk explanations, and evidence quality on `/agent`.
- [x] Update English and Chinese README documentation.
- [x] Add focused tests and run pytest, evals, Docker build, and CI push check.

## Success Criteria

- Agent responses include `data_source`, `risk_explanations`, and `evidence_quality`.
- README states that `data/testdata.xlsx` is the active static repository sample and the old crawler is preserved only in the undergraduate thesis branch.
- The app does not depend on the old crawler or live CNSTOCK access.
- Tests and evals remain deterministic without OpenAI.

## Review

- `data/testdata.xlsx`: 3,366 raw rows, 3,365 named bond rows, 3,363 valid yield records.
- Legacy CNSTOCK crawler URLs returned HTTP 403 to automated requests during verification on 2026-05-26.
- `python -m pytest -q`: passed, 25 tests.
- `python evals/run_agent_evals.py`: passed, 10/10 cases.
- `docker build -t bondlens-ai:ci .`: passed.
- `python app.py` smoke: `/agent` returned HTTP 200; `/api/agent/query` returned data source, risk explanations, and evidence quality.

# Portfolio Cleanup Todo

## Plan

- [x] Remove committed SQLite runtime database from `main`.
- [x] Remove legacy crawler code from `main`; keep it available through the preserved undergraduate thesis branch.
- [x] Remove legacy login, KDJ, report, comment, query, and visualization routes from the active Flask app.
- [x] Remove obsolete templates, static assets, README images, diagram scratch file, and language override files.
- [x] Slim runtime dependencies to the BondLens AI path.
- [x] Run lint, tests, agent evals, Docker build, and smoke checks.
- [x] Add ruff linting to GitHub Actions CI.
- [ ] Push cleanup and verify GitHub Actions.

## Success Criteria

- `main` presents BondLens AI as the only active app surface.
- No committed runtime database or stale user records remain in `main`.
- The current Agent still reads `data/testdata.xlsx`.
- The legacy thesis version remains available from `undergraduate-thesis-2024`.

## Review

- `python -m ruff check .`: passed.
- `python -m pytest -q`: passed, 25 tests.
- `python evals/run_agent_evals.py`: passed, 10/10 cases.
- `docker build --no-cache -t bondlens-ai:cleanup .`: passed.
- `python app.py` smoke: `/agent` returned HTTP 200, `/` returned HTTP 302 to `/agent`, `/api/agent/query` returned local static-sample analysis with `used_llm=false`.

# Live Bond Data Todo

## Plan

- [x] Make AkShare `bond_spot_deal` the default runtime data source.
- [x] Keep `data/testdata.xlsx` as the local fallback data source.
- [x] Add deterministic tests for live normalization and fallback behavior.
- [x] Keep CI and agent evals on static mode so external API instability does not break builds.
- [x] Update English and Chinese README documentation for live data, fallback, and environment controls.
- [x] Run lint, tests, evals, Docker build, and local smoke checks.
- [x] Push and verify GitHub Actions.

## Success Criteria

- Default app/API mode is `auto`: try AkShare live market data first, then fall back to `data/testdata.xlsx`.
- The `/agent` UI lets reviewers choose `auto`, `live`, or `static`.
- Agent responses identify the requested mode, actual runtime mode, provider, row counts, and fallback reason if live fetch fails.
- Tests do not require internet access.

## Review

- AkShare documentation confirms `bond_spot_deal` provides ChinaMoney current bond deal data with bond name, clean price, latest yield, BP change, weighted yield, and volume fields.
- Local `auto` mode smoke returned `runtime_mode=live`, `source_id=akshare_bond_spot_deal`, and more than 500 live rows.
- `python -m ruff check .`: passed.
- `python -m pytest -q --basetemp .tmp/pytest-live-<guid>`: passed, 29 tests.
- `python evals/run_agent_evals.py`: passed, 10/10 cases.
- `docker build -t bondlens-ai:live .`: passed.
- `docker compose up -d --build`: `/agent` returned HTTP 200, `/api/agent/query` returned live AkShare data, healthcheck was healthy, and `docker compose down` removed the container.
- GitHub Actions CI run `26430512616`: passed on `main` for commit `a20c7ae`.

# Local LLM Compatibility Todo

## Plan

- [x] Add OpenAI-compatible local endpoint support with `OPENAI_BASE_URL`.
- [x] Support both Responses API and Chat Completions so Ollama can run the LLM path.
- [x] Keep deterministic fallback when no API key and no local base URL are configured.
- [x] Add focused tests for local endpoint configuration and chat fallback.
- [x] Verify against the local Ollama service on `127.0.0.1:11434`.
- [x] Run lint, tests, evals, Docker build, and local smoke checks.
- [x] Push and verify CI.

## Success Criteria

- Setting `OPENAI_BASE_URL=http://127.0.0.1:11434/v1` and `OPENAI_MODEL=qwen2.5:1.5b` makes `llm_status=success`.
- Without `OPENAI_API_KEY` or `OPENAI_BASE_URL`, behavior remains `llm_status=disabled`.
- Tests do not require Ollama or internet access.

## Review

- Local Ollama was detected at `127.0.0.1:11434`; available models included `qwen2.5:1.5b` and `qwen3.5:9b`.
- `OPENAI_BASE_URL=http://127.0.0.1:11434/v1`, `OPENAI_MODEL=qwen2.5:1.5b`, and `OPENAI_API_STYLE=chat` returned `used_llm=True`, `llm_status=success`.
- Flask API smoke with local Ollama returned `used_llm=True`, `llm_status=success`, and included the disclaimer.
- Small local models can still paraphrase numeric evidence poorly, so structured `data_evidence` remains the source of truth. A future quality pass should add LLM faithfulness checks or keep LLM output as a sidecar enhancement.
- `python -m ruff check .`: passed.
- `python -m pytest -q --basetemp .tmp/pytest-llm-<guid>`: passed, 30 tests.
- `python evals/run_agent_evals.py`: passed, 10/10 cases.
- `docker build -t bondlens-ai:local-llm .`: passed.
- GitHub Actions CI run `26430905367`: passed on `main` for commit `43bfe90`.

# LLM Faithfulness Guardrail Todo

## Plan

- [x] Add a deterministic LLM numeric faithfulness guardrail.
- [x] Keep local Ollama available for smoke testing, not as the source of financial truth.
- [x] Return `llm_enhanced_answer`, `llm_guardrail`, `used_llm_in_final`, and `final_answer_source`.
- [x] Fall back to the deterministic report when the LLM output contains unsupported numeric claims.
- [x] Surface guardrail status in the Web UI and bilingual README.
- [x] Run lint, tests, evals, Docker build, and local Ollama smoke.
- [x] Push and verify CI.

## Success Criteria

- Unsupported numeric claims such as invented percentages are detected.
- If LLM output fails the guardrail, `final_answer_source` is `deterministic_fallback`.
- If LLM output passes the guardrail, `final_answer_source` is `llm`.
- Tests remain deterministic without Ollama or internet access.

## Review

- `python -m ruff check .`: passed.
- `python -m pytest -q --basetemp .tmp/pytest-guardrail-<guid>`: passed, 31 tests.
- `python evals/run_agent_evals.py`: passed, 10/10 cases.
- `docker build -t bondlens-ai:guardrail .`: passed.
- Local Ollama smoke with `qwen2.5:1.5b`: LLM call succeeded; guardrail rejected one generated answer and safely used `deterministic_fallback`.
- GitHub Actions CI run `26437352781`: passed on `main` for commit `f75e8d9`.

# Risk Language, Live Snapshot Cache, Red-team Eval Todo

## Plan

- [x] Extend LLM guardrail from numeric-only checks to numeric plus unsafe investment-language checks.
- [x] Add live AkShare snapshot cache so live failures fall back to the most recent successful live fetch before using the static Excel sample.
- [x] Add red-team evals for buy/sell advice, return guarantees, and overconfident safety wording.
- [x] Surface the new guardrail and snapshot state in the Web UI and bilingual README.
- [x] Push and verify CI.

## Success Criteria

- LLM outputs containing phrases such as `建议买入`, `非常安全`, `收益保证`, or `risk-free` cannot become the final answer.
- `auto`/`live` data mode uses this order: AkShare live fetch -> cached AkShare snapshot -> `data/testdata.xlsx`.
- Red-team evals fail if the deterministic answer starts giving investment recommendations or guaranteed-return language.
- CI runs unit tests, normal agent evals, red-team evals, and Docker build.

## Review

- `python -m ruff check .`: passed.
- `python -m pytest -q --cache-clear -o cache_dir=.tmp/pytest-cache --basetemp .tmp/pytest-risk-snapshot-redteam`: passed, 36 tests.
- `python evals/run_agent_evals.py`: passed, 10/10 cases.
- `python evals/run_red_team_evals.py`: passed, 3/3 red-team cases.
- `docker build -t bondlens-ai:risk-snapshot-redteam .`: passed.
- `docker compose up -d --build`: `/agent` returned HTTP 200, `/api/agent/query` returned HTTP 200, healthcheck was healthy.
- `docker compose down`: completed.
- GitHub Actions CI run `26438378150`: passed on `main` for commit `62e38ee`.
