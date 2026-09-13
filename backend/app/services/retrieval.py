"""BM25 retrieval over the JSON chunk index (pure stdlib, no ML deps).

Why BM25: zero downloads, runs on any laptop, deterministic, good enough for
keyword-heavy podcast transcripts. Trade-off documented in architecture.md:
no semantic matching; a future embedding index can sit behind the same
`retrieve()` signature.
"""
import json
import logging
import math
import re
from pathlib import Path

log = logging.getLogger("lenny.retrieval")
_TOKEN = re.compile(r"[a-z0-9']+")


def tokenize(s: str) -> list[str]:
    return _TOKEN.findall(s.lower())


class BM25Index:
    def __init__(self, records: list[dict]):
        self.records = records
        self.docs = [tokenize(r.get("text", "")) for r in records]
        self.doc_len = [len(d) for d in self.docs]
        self.avgdl = sum(self.doc_len) / max(1, len(self.doc_len))
        df: dict[str, int] = {}
        for d in self.docs:
            for t in set(d):
                df[t] = df.get(t, 0) + 1
        self.df = df
        self.n = len(self.docs)

    def score(self, query: str, k1: float = 1.5, b: float = 0.75) -> list[tuple[int, float]]:
        q = tokenize(query)
        scores = [0.0] * self.n
        for term in set(q):
            df = self.df.get(term, 0)
            if not df:
                continue
            idf = math.log(1 + (self.n - df + 0.5) / (df + 0.5))
            for i, doc in enumerate(self.docs):
                tf = doc.count(term)
                if not tf:
                    continue
                denom = tf + k1 * (1 - b + b * (self.doc_len[i] / max(1, self.avgdl)))
                scores[i] += idf * (tf * (k1 + 1) / denom)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(i, s) for i, s in ranked if s > 0]


_index_cache: BM25Index | None = None
_index_mtime: float = 0.0


def _load_records(index_path: str) -> list[dict]:
    p = Path(index_path)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8") or "[]")
    except Exception as e:  # noqa: BLE001
        log.warning("retrieval.bad-index err=%s", e)
        return []


def retrieve(query: str, index_path: str, top_k: int = 5) -> list[dict]:
    """Return [{source_id,title,url,chunk_index,text,score}]. Empty list when
    the index is empty or nothing matches (caller must handle gracefully)."""
    global _index_cache, _index_mtime
    records = _load_records(index_path)
    if not records:
        log.info("retrieval.empty-index query=%.60s", query)
        return []
    mtime = Path(index_path).stat().st_mtime
    if _index_cache is None or mtime != _index_mtime or len(_index_cache.records) != len(records):
        _index_cache = BM25Index(records)
        _index_mtime = mtime
    out = []
    for i, s in _index_cache.score(query)[:top_k]:
        r = records[i]
        out.append({**r, "score": round(float(s), 4)})
    log.info("retrieval query=%.60s hits=%d", query, len(out))
    return out
