# Design — The Lenny Growth Assistant

## 1. UX principles
1. **Answers first, provenance attached:** the answer is the hero; sources are one click away (expandable `[S1]` cards with title, URL/id, excerpt, score-ordered).
2. **No prompt literacy required:** example prompts on the empty state teach the three powers (ask → essay → artifact) by example.
3. **Honest states:** every async moment (thinking, generating, degraded backend, empty index) has a designed state — never a blank screen or a fake answer.
4. **Artifacts beside chat:** Claude-Artifacts-style side panel keeps conversational context visible while the deliverable renders.
5. **Trust is visible:** the active `provider / model` chip is always on screen; mock/fallback outputs are labelled.

## 2. Information architecture
```
┌──────────┬──────────────────────┬──────────────────┐
│ Sidebar  │ Chat thread          │ Artifact Viewer  │
│ - brand  │ - hero/examples      │ - kind + title   │
│ - new    │ - user/assistant     │ - Preview | Code │
│ - list   │ - source cards       │ - copy / close   │
│ - model  │ - composer           │ - empty/loading/ │
│          │                      │   error states   │
└──────────┴──────────────────────┴──────────────────┘
```

## 3. Key interaction states
- **Empty:** hero headline + 4 example prompts (PMF, loops, essay, artifact). Clicking sends immediately.
- **Loading:** three-dot typing bubble (aria-labelled); artifact panel shows "Generating artifact…".
- **Error:** composer-level alert + assistant message with the actionable fix (e.g. `ollama serve`); banner when backend degraded (DB/Ollama status).
- **Sources:** `<details>` cards per citation; excerpt + origin; expand independently.
- **Artifact:** Preview (rendered MD / sandboxed HTML) vs Code (raw + Copy → "Copied ✓"); ✕ collapses; "Show artifact" reopens.
- **Sessions:** list newest-first, active highlight, delete with immediate list update; "New chat" resets thread without reload.

## 4. Responsive behavior
- ≥1100px: 3-column grid (270px / 1fr / 430px).
- 720–1100px: artifact becomes a right-side overlay drawer (max 480px); empty viewer hidden to save space.
- <720px: single column; sidebar hidden (sessions accessible post-demo via desktop — noted limitation, sessions API fully usable); bubbles widen to 94%.

## 5. Accessibility
- Semantic landmarks (`aside`/`main`), labelled controls (composer label, send/close/copy aria-labels), `aria-live="polite"` thread, `role="alert"` errors, `role="tablist"` preview/code tabs.
- Keyboard: full flow (examples → input → send → details toggle → tabs) reachable by Tab/Enter; no keyboard traps.
- Contrast: light text on dark panels (≥4.5:1 for body); focus states via native outlines (kept, not reset).
- Motion: single subtle typing pulse; `prefers-reduced-motion` respected by keeping it opacity-only (no translation).

## 6. Design decisions (and why)
- **Dark editorial theme + amber accent:** "Lenny" warmth without newsletter cloning; amber reserved for primary actions and active states only.
- **react-markdown, no raw HTML:** chat markdown can never inject markup — a deliberate downgrade of power for safety.
- **Sandboxed iframe (no `allow-scripts`) for HTML:** chosen over `dangerouslySetInnerHTML` + DOMPurify-only, because iframe isolation also blocks exfiltration attempts that sanitizers can miss.
- **Composer placeholder as documentation:** lists all three capabilities in one line so users discover essay/artifact without a tutorial.
- **What was intentionally not built:** streaming tokens (typing indicator instead), rich text editor for artifacts (copy-out instead), light theme (scope control).
