"""Transcript ingestion: load -> clean -> chunk -> index (JSON + DB).

Source: https://github.com/ChatPRD/lennys-podcast-transcripts
Supports .txt / .md / .srt / .vtt / .json transcript dumps. Gracefully skips
empty or malformed files. Idempotent: re-running refreshes changed files only
if you pass --force, otherwise skips when index is newer than inputs.
"""
import json
import logging
import re
from pathlib import Path

log = logging.getLogger("lenny.ingest")

CHUNK_CHARS = 1200
CHUNK_OVERLAP = 200

_WS = re.compile(r"\s+")
_TS = re.compile(r"\d{1,2}:\d{2}(:\d{2})?(\.\d+)?\s*-->.*|\[\d{:.}\].*|^\d+\s*$", re.M)


def clean_text(raw: str) -> str:
    text = _TS.sub(" ", raw)
    text = text.replace("\r", "\n")
    text = _WS.sub(" ", text).strip()
    return text


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        # prefer to break on sentence boundary
        if end < len(text):
            cut = text.rfind(". ", start, end)
            if cut > start + size // 2:
                end = cut + 1
        piece = text[start:end].strip()
        if len(piece) > 100:
            chunks.append(piece)
        start = max(end - overlap, end) if end == len(text) else end - overlap
        if start <= 0 and end >= len(text):
            break
    return chunks


def parse_file(path: Path) -> tuple[str, str, str]:
    """Return (title, url, text). Never raises on malformed input."""
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:  # noqa: BLE001
        log.warning("ingest.skip unreadable=%s err=%s", path.name, e)
        return "", "", ""
    if path.suffix.lower() == ".json":
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                title = str(obj.get("title") or path.stem.replace("_", " ").title())
                url = str(obj.get("url") or obj.get("source_url") or "")
                text = str(obj.get("transcript") or obj.get("text") or "")
                return title, url, clean_text(text)
        except Exception as e:  # noqa: BLE001
            log.warning("ingest.skip bad-json=%s err=%s", path.name, e)
            return "", "", ""
        return "", "", ""
    title = path.stem.replace("_", " ").replace("-", " ").title()
    # First markdown H1 becomes title when present
    m = re.search(r"^#\s+(.+)$", raw, re.M)
    if m:
        title = m.group(1).strip()[:200]
    url_m = re.search(r"https?://\S+", raw)
    url = url_m.group(0).rstrip(").,") if url_m else ""
    return title, url, clean_text(raw)


def ingest(data_dir: str, index_path: str, force: bool = False) -> dict:
    src = Path(data_dir)
    idx = Path(index_path)
    files = sorted([p for p in src.rglob("*") if p.suffix.lower() in {".txt", ".md", ".srt", ".vtt", ".json"} and p.name.lower() != "readme.md"]) if src.exists() else []
    if not files:
        log.warning("ingest.empty data_dir=%s (add transcripts, see data/transcripts/README.md)", data_dir)
        idx.parent.mkdir(parents=True, exist_ok=True)
        if not idx.exists():
            idx.write_text("[]", encoding="utf-8")
        return {"files": 0, "chunks": 0, "skipped": 0}

    if idx.exists() and not force:
        newest_in = max(p.stat().st_mtime for p in files)
        if idx.stat().st_mtime >= newest_in:
            existing = json.loads(idx.read_text(encoding="utf-8") or "[]")
            log.info("ingest.cache-hit chunks=%d", len(existing))
            return {"files": len(files), "chunks": len(existing), "skipped": 0, "cached": True}

    records: list[dict] = []
    skipped = 0
    for path in files:
        title, url, text = parse_file(path)
        if not text or len(text) < 200:
            skipped += 1
            log.warning("ingest.skip too-short=%s len=%d", path.name, len(text))
            continue
        source_id = path.stem
        for i, ch in enumerate(chunk_text(text)):
            records.append({
                "source_id": source_id,
                "title": title,
                "url": url,
                "chunk_index": i,
                "text": ch,
            })
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    log.info("ingest.done files=%d chunks=%d skipped=%d", len(files), len(records), skipped)

    # Mirror into DB (best-effort; API works from JSON index even if DB is down)
    try:
        from ..database import SessionLocal
        from ..models import TranscriptChunk, TranscriptSource
        db = SessionLocal()
        try:
            for r in records:
                if not db.get(TranscriptSource, r["source_id"]):
                    db.add(TranscriptSource(id=r["source_id"], title=r["title"], url=r["url"]))
            db.query(TranscriptChunk).delete()
            db.add_all([TranscriptChunk(source_id=r["source_id"], chunk_index=r["chunk_index"], text=r["text"]) for r in records])
            db.commit()
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        log.warning("ingest.db-mirror failed (non-fatal): %s", e)

    return {"files": len(files), "chunks": len(records), "skipped": skipped}
