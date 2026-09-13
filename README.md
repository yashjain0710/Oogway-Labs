# The Lenny Growth Assistant

A full-stack, AI-powered conversational web app that turns **Lenny's Podcast transcripts** into grounded product & growth answers, **Ship 30 for 30-style essays**, and rendered **Markdown/HTML artifacts** — with local-first Ollama inference and a cloud toggle.

## Features
- Grounded chat (BM25 retrieval + citations `[S1..Sn]`, follow-ups, honest "not covered" path)
- Ship 30 for 30 essay skill (~1,250 words, hook → framework → action + sources)
- Artifact generation + in-app Artifact Viewer (Preview/Code, copy, sandboxed HTML)
- Sessions with independent context, persisted in PostgreSQL (SQLite fallback locally)
- Provider toggle: **Ollama (default)** | Anthropic | OpenAI | mock — env-only, no code changes
- Health endpoints, structured errors/logs, 15 automated tests, Docker Compose

## Architecture (short)
`React/Vite` → `FastAPI` → router → `chat | essay | artifact` skills → `BM25 retrieve()` + `providers.generate()` → `Postgres/SQLite`. Details: `docs/architecture.md`. PRD: `docs/PRD.md`. Design: `docs/design.md`.

## Prerequisites
- Python 3.11+, Node 20+
- [Ollama](https://ollama.com) for the local demo (+ a pulled model, e.g. `ollama pull phi3`)
- Docker (optional; enables one-command Postgres + full stack)

## Quick start — local, no Docker (5 min)
```bash
cp .env.example .env            # defaults: SQLite + ollama/qwen2.5:3b
pip install -r backend/requirements.txt
python -m backend.scripts.ingest --force
uvicorn backend.app.main:app --port 8000   # new terminal
cd frontend && npm install && npm run dev  # → http://localhost:5173
```
Ollama in another terminal: `ollama serve` + `ollama pull qwen2.5:3b` (match `OLLAMA_MODEL`/`LLM_MODEL` in `.env`; any local model — e.g. `phi3` — works).

## One-command startup — Docker (evaluator)
```bash
cp .env.example .env
docker compose up --build
# web http://localhost:5173 · api http://localhost:8000 · GET /health
```
The backend reaches host Ollama via `http://host.docker.internal:11434` (override with `OLLAMA_BASE_URL`). If Ollama isn't running, the UI shows an actionable error — no fake answers.

## Environment variables
| Var | Required | Default | Meaning |
|---|---|---|---|
| `DATABASE_URL` | no | `sqlite:///./lenny.db` | Postgres in Compose: `postgresql+psycopg2://lenny:lenny@db:5432/lenny` |
| `LLM_PROVIDER` | no | `ollama` | `ollama \| anthropic \| openai \| mock` |
| `LLM_MODEL` | no | `qwen2.5:3b` | Display name shown in UI |
| `OLLAMA_BASE_URL` | no | `http://localhost:11434` | Use `host.docker.internal` port inside Docker |
| `OLLAMA_MODEL` | no | `qwen2.5:3b` | Must be pulled (`ollama pull …`) |
| `OLLAMA_TIMEOUT_S` | no | `300` | Local inference timeout |
| `LLM_FALLBACK_ENABLED` / `LLM_FALLBACK_PROVIDER` | no | `false` / `anthropic` | Explicit, labelled cloud fallback only |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | for cloud | — | Anthropic provider |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | for cloud | — | OpenAI provider |
| `DATA_DIR` / `INDEX_PATH` | no | `./data/transcripts` / `./data/index/chunks.json` | Ingestion I/O |
| `FRONTEND_ORIGIN` | no | `http://localhost:5173` | CORS |

## Transcript ingestion
Official source: https://github.com/ChatPRD/lennys-podcast-transcripts
```bash
git clone https://github.com/ChatPRD/lennys-podcast-transcripts /tmp/lenny-tx
cp /tmp/lenny-tx/*.txt data/transcripts/   # adapt to actual layout
python -m backend.scripts.ingest --force
```
Pipeline: load (txt/md/srt/vtt/json) → strip timestamps → normalize → chunk (~1,200 chars/200 overlap) → `data/index/chunks.json` + DB mirror. Skips README/unreadable/<200-char files. Re-run is cache-aware (`--force` to rebuild). Bundled `data/transcripts/samples/` let the demo run offline.

## Cloud model setup
```bash
# .env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-…
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```
Restart the API; the sidebar chip and `GET /api/v1/settings/models` reflect the change. No code edits.

## API overview
`GET /health`, `GET /api/v1/health`, `POST/GET/GET/DELETE /api/v1/sessions…`, `POST /api/v1/chat`, `GET /api/v1/sessions/{id}/messages`, `POST/GET /api/v1/artifacts…`, `GET /api/v1/settings/models`. Errors: `{error, code, detail}`. Full table: `docs/architecture.md §4`.

## Testing
```bash
python -m pytest backend/tests -q        # 17 tests, mock LLM, temp SQLite — no keys/network
alembic -c backend/alembic.ini upgrade head   # formal migrations (startup also auto-creates with create_all)
```
Manual UI plan: `docs/manual-test-plan.md`.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `Ollama is not reachable` (503) | `ollama serve`, then `ollama pull <OLLAMA_MODEL>`; check `OLLAMA_BASE_URL` |
| `no model named …` (503) | `ollama pull` the exact `OLLAMA_MODEL` |
| Empty answers / "don't cover this" | Run ingest; check `GET /health` → `transcripts_indexed` > 0 |
| DB `unavailable` in health | Compose: `docker compose up db`; local: delete `lenny.db` and restart (re-created) |
| Frontend `Failed to fetch` | Backend must be on :8000; Vite proxies `/api` there |
| `npm install` blocked offline | UI is static — serve `frontend/` after a previous `npm run build`, or review `App.jsx` directly |

## Security notes
Generated HTML is untrusted: bleach allowlist server-side + `<iframe sandbox="">` (no scripts) client-side; Markdown never renders raw HTML; secrets never committed; CORS allowlisted. See `docs/architecture.md §8`.

## Extending
- Better recall → add an embedding index behind `retrieve()` (same return shape).
- Streaming → SSE on `/chat` + incremental renderer.
- SDK provider → implement `BaseProvider.generate` with the Claude Agent SDK and register in `get_provider()`.
- Auth → add user_id from a session cookie/JWT (column already exists).

## Known limitations
- BM25 has no semantic matching; paraphrased queries may miss.
- No token streaming yet; small local models answer slowly (~60–110 s per answer on this machine) but honestly.
- Small local models (3B) follow the essay skill's style rules imperfectly — structure, length, and sources are reliable, but an occasional throat-clearing opener or weaker prose can slip through. A cloud model (e.g. Claude) follows the Ship 30 rules tightly.
- Mobile hides the session sidebar (API-complete; responsive follow-up planned).
- Sample transcripts are paraphrased stand-ins until real ones are ingested.

## Demo video
Record 2–3 min (camera on): problem → product tour → local Ollama proof (`ollama list` + answer with citations) → one trade-off (e.g. BM25 vs embeddings). Upload to YouTube and link here + in the submission form.
