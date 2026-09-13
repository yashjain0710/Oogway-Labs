"""CLI: python -m backend.scripts.ingest [--force]"""
import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s :: %(message)s")

from backend.app.config import get_settings
from backend.app.services.ingestion import ingest


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest Lenny transcripts into data/index/chunks.json (+ DB mirror)")
    ap.add_argument("--force", action="store_true", help="Re-ingest even if index is newer than inputs")
    args = ap.parse_args()
    s = get_settings()
    result = ingest(s.DATA_DIR, s.INDEX_PATH, force=args.force)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
