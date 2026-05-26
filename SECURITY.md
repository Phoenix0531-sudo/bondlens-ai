# Security Policy

## Supported Version

The `main` branch is the supported version of BondLens AI. The `undergraduate-thesis-2024` branch is preserved for historical reference and is not maintained as a production system.

## Reporting Security Issues

Please open a GitHub issue with a concise description if the issue does not expose secrets or private data.

For sensitive reports, contact the repository owner directly through the GitHub profile before sharing details publicly.

## Data and API Key Handling

- Do not commit `.env`, API keys, local model credentials, database files, or runtime snapshots.
- The default live-data cache is stored under `.tmp/` and is ignored by Git.
- LLM calls are optional. The project must remain usable without OpenAI or Ollama credentials.

## Financial Safety Boundary

BondLens AI is not an investment advisory system. Reports of outputs that contain buy/sell recommendations, return guarantees, or risk-free claims should be treated as safety issues and covered by red-team evals.
