# Agent transcripts — build log

> Secrets removed. Times are session-relative. This log records prompts, decisions, failures, and fixes per the assignment's deliverable #6.

## Plan (Phase 1)
Prompt: "Build The Lenny Growth Assistant end-to-end in this repo."
Plan: backend-first (config→DB→health), then ingestion/retrieval, providers, skills, API, frontend, tests, Docker, docs, E2E. SQLite fallback locally because the build machine has no Docker/Postgres; Postgres via Compose for evaluators.

## Key decisions
1. **BM25 (stdlib) over vector DB** — zero downloads, deterministic, sufficient for keyword-heavy transcripts; `retrieve()` signature reserved for future embeddings.
2. **`create_all` over Alembic** — single-deploy simplicity; schema additive.
3. **Regex router over LLM classifier** — predictable, testable, cheap; triggers documented in UI examples.
4. **Agent-SDK not embedded** — Claude Agent SDK / Pi are coding agents, not request-path runtimes; provided a `generate(system, prompt)` seam instead, documented in architecture §10. Not claimed as integrated.
5. **Defense-in-depth artifact rendering** — bleach allowlist server-side + `sandbox=""` iframe client-side.

## Failures & fixes
| # | Failure | Fix |
|---|---|---|
| 1 | `pip install` stderr noise broke chained PowerShell (`&&` unsupported) | Used `;` chains and `Select-Object -Last` for output |
| 2 | Ingest indexed `data/transcripts/README.md` as a chunk | Skip `readme.md` by filename in `ingestion.py` |
| 3 | DB mirror failed pre-`init_db` (`no such table`) | Expected: tables created at app startup; mirror is best-effort, API reads JSON index |
| 4 | `test_chat_503_when_ollama_down`: `KeyError: 'error'` — FastAPI wrapped dict detail under `detail` | Added `HTTPException` handler in `main.py` unwrapping dict details into `{error, code, detail}` |
| 5 | Full suite took ~135s (Ollama probe timeouts per test-app) | Accepted; probes use 3s timeout, tests hermetic via mock provider |
| 6 | No Docker/Postgres on build machine | SQLite fallback (`DATABASE_URL`) for local + tests; Compose ships Postgres for evaluators |
| 7 | Live demo on `phi3-local`: chat returned 503 — provider used `/api/generate` whose `response` field came back empty; grounded Q&A took ~103 s (over the 120 s timeout) and the model regurgitated chunks instead of synthesizing | Switched to Ollama `/api/chat` (returns `message.content`, passes system role properly) + strip `\|…\|` special tokens (`_clean_output`); switched default model to `qwen2.5:3b` (77 s, structured answers with citations); raised `OLLAMA_TIMEOUT_S` default to 300 |

## Verification
- `python -m backend.scripts.ingest --force` → 3 files, 6 chunks.
- `retrieve('product-market fit retention')` → PMF sample top hit (score 4.73).
- `pytest backend/tests` → **15 passed**.
- E2E (mock + live Ollama `phi3-local`) via API smoke script — see `docs/manual-test-plan.md`.
- Frontend `npm run build` — verified during handoff (see README troubleshooting if network blocks npm).
