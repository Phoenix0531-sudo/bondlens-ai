# Modern AI Bond Agent Upgrade Todo

## Plan

- [x] Preserve original thesis state with `legacy-thesis-2024` branch and `thesis-submission-2024-04-24` tag.
- [x] Create and switch to `modern-ai-bond-agent` for all upgrade work.
- [x] Fix Flask startup issues, missing imports, secret key handling, dependencies, and minimal SQLite initialization.
- [ ] Extract bond data loading and local analysis tools into `bond_agent/`.
- [ ] Add a single Bond Analyst Agent with tool trace and deterministic fallback output.
- [ ] Add Web/API entry points for the agent without rewriting the legacy UI.
- [ ] Add focused tests for data loading, tools, fallback agent output, and Flask smoke routes.
- [ ] Add Docker support, `.env.example`, and professional README documentation.
- [ ] Verify local startup, tests, Docker build, and Docker-served app access.

## Review

Pending.
