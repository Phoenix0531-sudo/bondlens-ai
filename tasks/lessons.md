# Project Lessons

- Preserve/review boundaries before coding: confirm branch, original tag/branch protection, and push expectations before modifying files.
- For commit-ready review passes, keep cleanup deletes separate from feature commits so large resource removals do not hide Agent code changes.
- Special-character search tests should assert plain-text handling and no regex errors, not assume every special character must return zero matches.
- Portfolio UI should not expose raw JSON or code-like diagnostics by default; keep those in API/schema endpoints or optional developer views, and make the main page evidence-led.
