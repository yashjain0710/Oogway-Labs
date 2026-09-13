# PRD — The Lenny Growth Assistant

## 1. User and problem
**Primary user:** a product or growth team member (PM, growth lead, founder) who wants practical, trustworthy advice distilled from Lenny's Podcast without manually hunting through dozens of transcripts or learning prompt engineering.

**Job to be done:** "When I face a product/growth decision, I want a grounded answer with reusable written output (essay, strategy doc, page mock) in one place, so I can act or share it in minutes."

**Pain removed:**
- Searching raw transcripts is slow and yields quotes without synthesis.
- Generic chatbots hallucinate Lenny-isms with no provenance.
- Turning advice into a publishable essay or a shareable doc/page takes a second tool and re-prompting.

## 2. Success metrics (measurable)
1. **Evaluator reproducibility:** a fresh clone reaches a working chat (health `ok`) in ≤10 min following README only.
2. **Groundedness:** ≥90% of sampled answers on seeded topics include ≥1 transcript citation; 0 fabricated episode claims in review.
3. **Session integrity:** follow-up questions resolve in the same session context across a 5-turn script (manual test plan passes).
4. **Content + artifact completion:** essay (~1,100–1,400 words, hook, headings, takeaway, sources) and one Markdown + one HTML artifact render in-viewer.
5. **Quality gate:** `pytest backend/tests` — 15/15 pass; local Ollama demo works with no cloud key.

## 3. Assumptions (labelled)
- **A1:** Evaluator has Python 3.11+, Node 20+, and Ollama installed; Docker optional (SQLite fallback documented).
- **A2:** Official transcript repo layout is plain text/markdown files; the pipeline accepts txt/md/srt/vtt/json so layout drift is tolerated.
- **A3:** `qwen2.5:3b` (or any small Ollama model) is "good enough" for grounded synthesis; BM25 retrieval is "good enough" vs. embeddings for keyword-rich transcripts.
- **A4:** Single local user (`local-user`); no auth/SSO needed for the demo.
- **A5:** Sample transcripts are paraphrased stand-ins; evaluator can drop real transcripts in `data/transcripts/` and re-ingest.

## 4. Scope
**Included:** grounded chat with citations + follow-ups; independent sessions (CRUD) persisted in Postgres/SQLite; Ship 30 for 30 essay skill; Markdown + HTML artifact generation with sandboxed viewer; Ollama default + Anthropic/OpenAI toggle visible in UI; ingestion CLI + refresh; health/settings endpoints; structured errors/logs; tests; Docker Compose; docs + demo script.
**Excluded (and why):** user auth/SSO (single-user demo, adds ops cost); embeddings/vector DB (heavy downloads, marginal gain on this corpus — interface reserved); streaming tokens (polling-free simplicity; can add SSE later); multi-language UI (English corpus); fine-tuning (out of scope for a deployment brief).

## 5. User flows
1. **Ask:** land → example prompt or own question → grounded answer + [S1..Sn] expandable sources → follow-up stays in session.
2. **Essay:** "Turn this into a Ship 30 essay" → routed to essay skill → ~1,250-word essay with hook/headings/takeaway/sources.
3. **Artifact:** "Create a Markdown/HTML …" → artifact skill → renders in Artifact Viewer (Preview/Code tabs, copy) → persists, re-openable.
4. **Switch model:** provider/model shown in sidebar; change `.env` → restart → `/settings/models` reflects it.

## 6. Acceptance criteria
- `GET /health` + `GET /api/v1/health` report db/ollama/provider/index counts.
- New chat creates independent context; sessions list/switch/delete work; messages persist with timestamps.
- Every grounded answer carries source title/id/excerpt/score; empty retrieval returns an honest "not covered" message.
- Essay meets Ship 30 structure + word-count band + sources; no fabricated quotes.
- HTML artifacts render script-free in a sandboxed iframe; `<script>`/`on*`/`javascript:` payloads are stripped (tested).
- Missing Ollama → actionable 503 (how to start/pull), never a fake answer; no silent cloud fallback.
- No secrets committed (`.env.example` only); fresh-clone run works per README.

## 7. Risks and trade-offs
| Risk | Likelihood / impact | Mitigation |
|---|---|---|
| Hallucination of episode claims | High / High | System prompt grounding contract; citations mandatory; honest empty-retrieval path |
| Local-model quality (small Ollama) | High / Med | Low temperature, short focused answers, retrieval does the heavy lifting; cloud toggle for quality; style rule violations documented as a known limitation |
| Latency (local inference) | Med / Med | Typing indicator; 120s timeout; top_k ≤ 10; BM25 is instant |
| Cost (cloud APIs) | Low / Med | Ollama default; cloud keys optional; no background jobs |
| Unsafe artifact HTML | Med / High | Server bleach allowlist + client `sandbox=""` iframe (defense in depth); tests with payloads |
| Data leakage (secrets) | Low / High | `.env` gitignored, `.env.example` safe defaults, no prompt/secret echo |
| DB unavailable | Low / Med | Boot continues degraded; health reports; structured 5xx; SQLite fallback locally |
| Stale/empty index | Med / Med | Ingest CLI with `--force`, cache-aware refresh, index count in health + README |

## 8. Implementation plan (as executed)
1. Backend skeleton: config, DB models, health, error envelope.
2. Ingestion (clean/chunk/index + DB mirror) with sample transcripts; BM25 retrieval.
3. Provider abstraction (Ollama/Anthropic/OpenAI/mock) + router + chat/essay/artifact skills.
4. REST sessions/chat/artifacts/settings; persistence verified.
5. React+Vite UI: chat, sources, sessions, model chip, Artifact Viewer.
6. Tests (15), Docker Compose, docs, E2E verification (mock + real Ollama).
