"""DB engine/session. Supports Postgres (Docker) and SQLite (local fallback)."""
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import get_settings

log = logging.getLogger("lenny.db")
Base = declarative_base()


def _connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def get_engine():
    url = get_settings().DATABASE_URL
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update({"pool_size": 5, "max_overflow": 10})
    return create_engine(url, **kwargs)


engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)
    Base.metadata.create_all(bind=engine)
    log.info("db.init ok url=%s", _redact(get_settings().DATABASE_URL))


def _redact(url: str) -> str:
    # Never log passwords
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            _, host = rest.rsplit("@", 1)
            return f"{scheme}://***@{host}"
    return url
