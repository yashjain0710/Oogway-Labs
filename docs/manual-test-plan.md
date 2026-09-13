# Manual UI test plan (5–10 min, no automation needed)

Backend must be running (`uvicorn backend.app.main:app`) and frontend (`npm run dev` → http://localhost:5173).

| # | Action | Expect |
|---|---|---|
| 1 | Open app fresh | Hero + 4 example prompts; sidebar shows `ollama / qwen2.5:3b` (or your model) |
| 2 | Click "product-market fit" example | Typing indicator → grounded answer with ≥1 expandable [S1] source card |
| 3 | Follow up: "What metric matters most?" | Answer stays on topic (session context); same session, 4 messages in history after reload |
| 4 | New chat → ask about onboarding | Independent context; session list shows 2 chats; switching restores each history |
| 5 | "Turn the lessons into a Ship 30 for 30-style essay." | ~1,100–1,400-word essay: hook, ## headings, bullets, bold takeaways, Sources section |
| 6 | "Create a Markdown product strategy document from this conversation." | Artifact Viewer opens: Preview renders doc; Code shows source; Copy works |
| 7 | "Render this as an HTML landing page." | Styled page in viewer; view-source shows no `<script>` / `on*` handlers |
| 8 | Stop Ollama, send a message | Actionable error naming `ollama serve` / `ollama pull`; no fake answer |
| 9 | Resize to 900px then 400px | Artifact becomes overlay drawer; mobile single column, bubbles readable |
| 10 | Keyboard only: Tab to input, type, Enter | Message sends; sources expand via keyboard; tabs switch Preview/Code |

Record pass/fail + model used. Any hallucinated episode claim = fail.
