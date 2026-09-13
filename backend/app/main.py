"""FastAPI app: logging, CORS, health, error envelope."""
import json
import logging
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as FastHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .api.routes import router
from .config import get_settings
from .database import engine, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
                    stream=sys.stdout)
log = logging.getLogger("lenny.app")


def create_app() -> FastAPI:
    app = FastAPI(title="The Lenny Growth Assistant", version="1.0.0")
    s = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[s.FRONTEND_ORIGIN, "http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
    )

    @app.exception_handler(FastHTTPException)
    async def http_envelope(_: Request, exc: FastHTTPException):
        # Unwrap dict details so clients always see {error, code, detail}
        if isinstance(exc.detail, dict):
            return JSONResponse(exc.detail, status_code=exc.status_code)
        return JSONResponse({"error": str(exc.detail), "code": "http_error", "detail": None},
                            status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception):
        if hasattr(exc, "status_code"):
            raise exc
        log.exception("unhandled error")
        return JSONResponse({"error": "Internal server error", "code": "internal",
                             "detail": None}, status_code=500)

    @app.on_event("startup")
    def _startup():
        try:
            init_db()
        except Exception as e:  # noqa: BLE001 — DB down must not crash boot; health reports it
            log.warning("db.init failed (health will report degraded): %s", e)

    def _checks() -> dict:
        # DB check
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            db = "ok"
        except Exception as e:  # noqa: BLE001
            db = f"unavailable: {type(e).__name__}"
        # Ollama check (short timeout)
        import httpx
        try:
            r = httpx.get(get_settings().OLLAMA_BASE_URL.rstrip("/") + "/api/tags", timeout=3)
            ollama = "ok" if r.status_code < 500 else f"degraded: {r.status_code}"
        except Exception:  # noqa: BLE001
            ollama = "unavailable (start with `ollama serve`)"
        # Index size
        try:
            p = Path(get_settings().INDEX_PATH)
            n = len(json.loads(p.read_text(encoding="utf-8"))) if p.exists() else 0
        except Exception:  # noqa: BLE001
            n = 0
        st = get_settings()
        return {"database": db, "ollama": ollama, "provider": st.LLM_PROVIDER,
                "model": st.LLM_MODEL, "transcripts_indexed": n}

    @app.get("/health")
    def health():
        c = _checks()
        status = "ok" if c["database"] == "ok" else "degraded"
        return {"status": status, **c}

    app.include_router(router)

    @app.get("/api/v1/health")
    def health_v1():
        c = _checks()
        status = "ok" if c["database"] == "ok" else "degraded"
        return {"status": status, **c}

    return app


app = create_app()
