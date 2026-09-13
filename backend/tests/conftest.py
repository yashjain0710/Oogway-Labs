"""Pytest bootstrap: isolated SQLite DB + mock LLM + sample index."""
import json
import os
import tempfile

import pytest

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
_idx = tempfile.NamedTemporaryFile(suffix=".json", delete=False)

os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["LLM_MODEL"] = "test-mock"
os.environ["INDEX_PATH"] = _idx.name

_idx.write(json.dumps([
    {"source_id": "pmf", "title": "PMF Episode", "url": "https://example.com/pmf",
     "chunk_index": 0, "text": "Product-market fit shows in retention curves that flatten. The forty percent survey threshold signals disappointment if the product went away."},
    {"source_id": "loops", "title": "Growth Loops Episode", "url": "https://example.com/loops",
     "chunk_index": 0, "text": "Growth loops reinvest output. A content loop compounds when users create content that brings new users who create more content."},
]).encode())
_idx.close()

from backend.app.database import init_db  # noqa: E402

init_db()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    with TestClient(create_app()) as c:
        yield c
