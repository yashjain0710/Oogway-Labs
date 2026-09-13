# Architecture — The Lenny Growth Assistant

## 1. System overview
```
Browser (React+Vite :5173) ──REST/JSON──▶ FastAPI (:8000) ──▶ Postgres (Docker) / SQLite (local fallback)
        │                                    ├─ router → chat | essay | artifact skills
        │                                    ├─ providers: ollama (default) | anthropic | openai | mock
        │                                    └─ BM25 retrieval over data/index/chunks.json
        └─ Artifact Viewer: MD via safe renderer; HTML via <iframe sandbox="">
```
One-command Docker: `docker compose up --build` (db + api + web). Local no-Docker: `uvicorn` + `npm run dev` with SQLite.

## 2. Component boundaries
- `backend/app/main.py` — app factory, CORS, health (`/` + `/api/v1/health`), HTTPException envelope, degraded-boot (DB failure never crashes startup).
- `backend/app/config.py` — `Settings` (pydantic-settings); model switch = env only.
- `backend/app/database.py` — engine/session, `init_db()` (`create_all` at startup for single-deploy simplicity); formal migration path is Alembic (`backend/alembic`, `alembic upgrade head`).
- `backend/app/models.py` — `sessions`, `messages`, `transcript_sources`, `transcript_chunks`, `artifacts`.
- `backend/app/api/routes.py` — sessions CRUD, chat, artifacts, settings/models.
- `backend/app/services/ingestion.py` — load/clean/chunk/index + DB mirror; skips README, unreadable/short files; cache-aware refresh.
- `backend/app/services/retrieval.py` — pure-stdlib BM25; `retrieve()` returns source_id/title/url/chunk/score; hot-reloads on index mtime.
- `backend/app/services/providers.py` — `BaseProvider` + 4 providers; `ProviderError` (retriable flag); `available_models()`.
- `backend/app/services/router.py` — regex router (essay/artifact/chat), logged, unit-tested.
- `backend/app/services/chat.py` — grounding contract system prompt, history window (last 6), [Sn] citations, honest empty path.
- `backend/app/services/essay.py` — Ship 30 principles encoded as a reusable system prompt (hook, one idea, framework, skimmable, specifics, action, ~1,250 words).
- `backend/app/services/artifacts.py` — md/html generation + `sanitize_html` (bleach allowlist) + title extraction.
- `frontend/src/` — `api.js`, `App.jsx` (sessions/chat/composer), `components.jsx` (Md + ArtifactViewer).

## 3. Database schema
- `sessions(id PK, title, user_id, created_at, updated_at)` — one row per chat; independent context.
- `messages(id PK, session_id FK→sessions, role, content, sources_json, route, created_at)` — full history; sources stored as JSON for audit.
- `transcript_sources(id PK=filename slug, title, url, created_at)`.
- `transcript_chunks(id PK, source_id FK, chunk_index, text)`.
- `artifacts(id PK, session_id FK nullable, title, kind, content, created_at)`.

## 4. API endpoints
| Method & path | Purpose | Errors |
|---|---|---|
| GET `/health`, GET `/api/v1/health` | db/ollama/provider/index status | 200 always (status ok/degraded) |
| POST `/api/v1/sessions` | create session | 422 validation |
| GET `/api/v1/sessions` | list (50, newest first) | — |
| GET `/api/v1/sessions/{id}` | one session | 404 |
| DELETE `/api/v1/sessions/{id}` | delete + cascade messages | 404 |
| POST `/api/v1/chat` | route → skill → persist user+assistant | 404 session, 422, 503 provider |
| GET `/api/v1/sessions/{id}/messages` | history | 404 |
| POST `/api/v1/artifacts` | direct artifact generation | 422, 503 |
| GET `/api/v1/artifacts/{id}` | fetch artifact | 404 |
| GET `/api/v1/settings/models` | active provider/model + flags | — |
Response envelope for errors: `{error, code, detail}` (HTTPException dict-detail unwrapped in `main.py`).

## 5. Ingestion / retrieval flow
1. `python -m backend.scripts.ingest [--force]` scans `DATA_DIR` (txt/md/srt/vtt/json), extracts title (H1 or filename) + first URL, strips timestamps, normalizes whitespace.
2. Chunks ≈1,200 chars / 200 overlap, sentence-boundary cut, drops <100-char tails.
3. Writes `INDEX_PATH` (JSON records) + best-effort DB mirror. Ingest is idempotent and cache-aware (skips when index newer).
4. `retrieve()` tokenizes, BM25-scores (k1=1.5, b=0.75), returns top_k with scores; empty index → `[]` → honest "not covered" answer.

## 6. Agent routing
Keyword router (not autonomous): essay patterns (`ship 30|essay|1250 words|blog post`) → `essay.write_essay`; artifact patterns (`artifact|render as html|markdown doc|strategy document|landing page|create a …`) → `artifacts.generate_artifact` (+persist); else grounded `chat.answer_question`. Decision logged (`lenny.router`) and covered by boundary tests.

## 7. Model toggle & fallback
`LLM_PROVIDER` ∈ ollama|anthropic|openai|mock; per-provider model vars; UI chip reads `/settings/models`. Ollama failures raise `ProviderError` with `ollama serve`/`ollama pull` instructions → HTTP 503. Cloud fallback only when `LLM_FALLBACK_ENABLED=true` (explicit, labelled `[fallback:…]` in output) — never silent.

## 8. Security
- Generated HTML = untrusted: server `sanitize_html` (strip `<script>`, `on*` handlers, `javascript:` URLs; bleach allowlist of 20 tags/6 attr groups) **plus** client `<iframe sandbox="">` with no `allow-scripts` — defense in depth; payload tests included.
- Markdown rendered via react-markdown (no raw-HTML plugin). No `dangerouslySetInnerHTML` anywhere.
- Secrets: `.env` ignored, only `.env.example` committed; DB URL redacted in logs; no prompt/key echo in responses.
- CORS restricted to configured frontend origins.

## 9. Deployment topology
- **Docker (evaluator):** `db` (postgres:16, volume pgdata, healthcheck) → `api` (waits healthy, runs ingest then uvicorn) → `web` (nginx serving dist). Host Ollama reached via `host.docker.internal:11434`.
- **Local (no Docker):** Postgres→SQLite fallback via `DATABASE_URL`; backend `uvicorn`, frontend `vite dev` (proxy `/api`→:8000).
- **Observability:** structured `logging` per module (router decisions, retrieval hits, provider outcomes, session ids); health exposes db/ollama/index counts.
- **Resilience:** degraded boot; 503s with fixes; empty-retrieval honesty; timeouts (Ollama 120s, cloud 90s, health probe 3s).

## 10. Trade-offs (key)
- **BM25 over embeddings:** zero downloads/determinism/simplicity vs. no semantic recall. Mitigation: same `retrieve()` signature allows a future embedding index.
- **`create_all` over Alembic migrations:** one-deploy simplicity vs. long-term migration discipline. Schema is additive; Alembic can be introduced without API change.
- **Regex router over LLM classifier:** predictable/testable/cheap vs. less flexible phrasing. Skill triggers are documented in UI examples.
- **No token streaming:** simpler state machine; typing indicator covers perceived latency. SSE is the natural next increment.
- **Agent-SDK decision:** the Claude Agent SDK / Pi agent are coding agents, not request-path runtimes; embedding them would add weight without product value. The provider interface (`generate(system, prompt)`) is the documented seam where an SDK-backed provider can be added later — not claimed as integrated.
