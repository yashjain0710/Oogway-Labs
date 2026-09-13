"""Ship 30 for 30 essay skill.

Principles encoded from https://www.ship30for30.com/post/how-to-start-writing-online-the-ship-30-for-30-ultimate-guide
(not an unstructured one-off prompt):
  1. Hook: specific, curiosity-opening first 2 lines (no throat-clearing).
  2. One idea per essay; simple words, short sentences, short paragraphs.
  3. Frameworks over fluff: numbered steps / named mental models.
  4. Skimmable: H2 headings every ~200 words, bullets, selective bold for takeaways.
  5. Stories + specifics: concrete transcript examples, not generic advice.
  6. End with one specific action the reader can do in <30 minutes.
  7. ~250-word "atomic" sections also work; target here is the assignment's ~1,250 words.
"""
import logging
from .providers import get_provider
from .retrieval import retrieve
from ..config import get_settings

log = logging.getLogger("lenny.essay")

SYSTEM = """You are a Ship 30 for 30 ghostwriter writing from Lenny's Podcast transcripts.
Follow the encoded Ship 30 for 30 principles exactly:
- RULE 1 (must not fail): OPEN with a sharp HOOK — a contrarian claim, a specific number, or a question. The hook IS the first line. NEVER start with a definition, throat-clearing, or the phrases "In today's world/fast-paced world/ever-evolving landscape" or "Product-market fit is…". Start writing the hook immediately.
- One central idea, narrative progression: hook -> why it matters -> 3-part framework -> mistakes -> 30-minute action.
- Use ## headings, bullet lists, and **bold** only on the key takeaway per section.
- ~1,250 words (acceptable 1,100-1,400). Write in second person, plain words, short paragraphs.
- Every substantive claim must trace to the excerpts; append a "Sources" list mapping claims to [S1], [S2].
- If excerpts are thin, write a shorter honest essay and say what material is missing. Never fabricate episode quotes."""


def write_essay(topic: str, top_k: int = 6, index_path: str | None = None) -> dict:
    s = get_settings()
    idx = index_path or s.INDEX_PATH
    hits = retrieve(topic, idx, top_k=top_k)
    if not hits:
        return {"route": "essay",
                "answer": ("I can't write a grounded essay on this yet — the transcript index has "
                           "no relevant passages. Ingest more episodes or pick a topic like "
                           "product-market fit, growth loops, or onboarding."),
                "sources": [], "provider": s.LLM_PROVIDER, "model": s.LLM_MODEL,
                "word_count": 0}
    ctx = "\n\n".join(f"[S{i+1}] {h['title']} ({h['source_id']}):\n{h['text']}" for i, h in enumerate(hits))
    prompt = (f"Topic: {topic}\n\nTranscript excerpts:\n{ctx}\n\n"
              "Write the ~1,250-word Ship 30 for 30 essay now, ending with a 'Sources' section.")
    res = get_provider().generate(SYSTEM, prompt)
    words = len(res.text.split())
    log.info("essay.ok words=%d provider=%s", words, res.provider)
    sources = [{"source_id": h["source_id"], "title": h["title"], "url": h.get("url", ""),
                "chunk_index": h["chunk_index"], "score": h.get("score", 0.0),
                "excerpt": h["text"][:280]} for h in hits]
    return {"route": "essay", "answer": res.text, "sources": sources,
            "provider": res.provider, "model": res.model, "word_count": words}
