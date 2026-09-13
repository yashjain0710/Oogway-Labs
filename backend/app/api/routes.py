"""REST API v1: sessions, chat, artifacts, settings, health."""
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from .. import models, schemas
from ..config import get_settings
from ..database import get_db
from ..services import artifacts as artifact_skill
from ..services import chat as chat_skill
from ..services import essay as essay_skill
from ..services.providers import ProviderError, available_models, get_provider
from ..services.router import route_message

log = logging.getLogger("lenny.api")
router = APIRouter(prefix="/api/v1")


def _iso(dt) -> str:
    return dt.isoformat() if dt else ""


def _sources(obj) -> list:
    try:
        return json.loads(obj or "[]")
    except Exception:  # noqa: BLE001
        return []


@router.post("/sessions", response_model=schemas.SessionOut, status_code=201)
def create_session(body: schemas.SessionCreate, db: DBSession = Depends(get_db)):
    s = models.Session(title=body.title, user_id=body.user_id)
    db.add(s)
    db.commit()
    db.refresh(s)
    log.info("session.create id=%s", s.id)
    return schemas.SessionOut(id=s.id, title=s.title, user_id=s.user_id,
                              created_at=_iso(s.created_at), updated_at=_iso(s.updated_at))


@router.get("/sessions", response_model=list[schemas.SessionOut])
def list_sessions(db: DBSession = Depends(get_db)):
    rows = db.query(models.Session).order_by(models.Session.updated_at.desc()).limit(50).all()
    out = []
    for r in rows:
        n = db.query(models.Message).filter_by(session_id=r.id).count()
        out.append(schemas.SessionOut(id=r.id, title=r.title, user_id=r.user_id,
                                      created_at=_iso(r.created_at), updated_at=_iso(r.updated_at),
                                      message_count=n))
    return out


@router.get("/sessions/{session_id}", response_model=schemas.SessionOut)
def get_session(session_id: str, db: DBSession = Depends(get_db)):
    r = db.get(models.Session, session_id)
    if not r:
        raise HTTPException(404, {"error": "Session not found", "code": "not_found"})
    n = db.query(models.Message).filter_by(session_id=session_id).count()
    return schemas.SessionOut(id=r.id, title=r.title, user_id=r.user_id,
                              created_at=_iso(r.created_at), updated_at=_iso(r.updated_at), message_count=n)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, db: DBSession = Depends(get_db)):
    r = db.get(models.Session, session_id)
    if not r:
        raise HTTPException(404, {"error": "Session not found", "code": "not_found"})
    db.delete(r)
    db.commit()
    log.info("session.delete id=%s", session_id)
    return None


@router.get("/sessions/{session_id}/messages", response_model=list[schemas.MessageOut])
def list_messages(session_id: str, db: DBSession = Depends(get_db)):
    if not db.get(models.Session, session_id):
        raise HTTPException(404, {"error": "Session not found", "code": "not_found"})
    rows = db.query(models.Message).filter_by(session_id=session_id).order_by(models.Message.created_at).all()
    return [schemas.MessageOut(id=m.id, role=m.role, content=m.content, route=m.route or "chat",
                               sources=_sources(m.sources_json), created_at=_iso(m.created_at)) for m in rows]


@router.post("/chat", response_model=schemas.ChatResponse)
def chat(body: schemas.ChatRequest, db: DBSession = Depends(get_db)):
    s = get_settings()
    session = db.get(models.Session, body.session_id) if body.session_id else None
    if body.session_id and not session:
        raise HTTPException(404, {"error": "Session not found", "code": "not_found"})
    if not session:
        session = models.Session(title=body.message[:60] or "New chat")
        db.add(session)
        db.commit()
        db.refresh(session)

    db.add(models.Message(session_id=session.id, role="user", content=body.message, route="pending"))
    db.commit()

    history_rows = db.query(models.Message).filter_by(session_id=session.id).order_by(models.Message.created_at).all()
    history = [{"role": m.role, "content": m.content} for m in history_rows if m.role in ("user", "assistant")]

    route = route_message(body.message)
    try:
        if route == "essay":
            result = essay_skill.write_essay(body.message, top_k=body.top_k + 1)
        elif route == "artifact":
            convo = "\n".join(f"{h['role']}: {h['content'][:400]}" for h in history[-8:])
            art = artifact_skill.generate_artifact(body.message, convo)
            row = models.Artifact(session_id=session.id, title=art["title"], kind=art["kind"], content=art["content"])
            db.add(row)
            db.commit()
            db.refresh(row)
            history_ctx = f"\n\nView it in the Artifact Viewer (id `{row.id}`)."
            result = {"route": "artifact",
                      "answer": f"Created **{art['title']}** ({art['kind']}).{history_ctx}",
                      "sources": [], "provider": art["provider"], "model": art["model"],
                      "artifact_id": row.id}
            result_artifact_id = row.id
        else:
            result = chat_skill.answer_question(body.message, history, top_k=body.top_k)
            result_artifact_id = None
    except ProviderError as e:
        log.warning("chat.provider-error route=%s err=%s", route, e)
        # Explicit 503 with actionable message; optional configured fallback (never silent)
        if s.LLM_FALLBACK_ENABLED and s.LLM_PROVIDER == "ollama":
            try:
                fb = get_provider(s.LLM_FALLBACK_PROVIDER)
                fres = fb.generate("You are a helpful product advisor.", body.message[:2000])
                result = {"route": route, "answer": f"[fallback:{fres.provider}] {fres.text}",
                          "sources": [], "provider": fres.provider, "model": fres.model}
                result_artifact_id = None
            except ProviderError as e2:
                raise HTTPException(503, {"error": str(e), "code": "provider_unavailable",
                                          "detail": f"Fallback also failed: {e2}"}) from e2
        else:
            raise HTTPException(503, {"error": str(e), "code": "provider_unavailable"}) from e

    result_artifact_id = result.get("artifact_id", result_artifact_id if route == "artifact" else None)
    db.add(models.Message(session_id=session.id, role="assistant", content=result["answer"],
                          sources_json=json.dumps(result.get("sources", [])), route=result.get("route", route)))
    session.title = (body.message[:60] if session.title == "New chat" else session.title)
    db.commit()
    log.info("chat.ok session=%s route=%s provider=%s", session.id, result.get("route"), result.get("provider"))
    return schemas.ChatResponse(session_id=session.id, route=result.get("route", route),
                                answer=result["answer"], sources=result.get("sources", []),
                                model=result.get("model", s.LLM_MODEL),
                                provider=result.get("provider", s.LLM_PROVIDER),
                                artifact_id=result_artifact_id)


@router.post("/artifacts", response_model=schemas.ArtifactOut, status_code=201)
def create_artifact(body: schemas.ArtifactCreate, db: DBSession = Depends(get_db)):
    convo = ""
    if body.session_id:
        rows = db.query(models.Message).filter_by(session_id=body.session_id).order_by(models.Message.created_at).all()
        convo = "\n".join(f"{m.role}: {m.content[:400]}" for m in rows[-8:])
    try:
        art = artifact_skill.generate_artifact(body.prompt, convo, kind=body.kind)
    except ProviderError as e:
        raise HTTPException(503, {"error": str(e), "code": "provider_unavailable"}) from e
    row = models.Artifact(session_id=body.session_id, title=body.title if body.title != "Untitled artifact" else art["title"],
                          kind=art["kind"], content=art["content"])
    db.add(row)
    db.commit()
    db.refresh(row)
    return schemas.ArtifactOut(id=row.id, title=row.title, kind=row.kind, content=row.content, created_at=_iso(row.created_at))


@router.get("/artifacts/{artifact_id}", response_model=schemas.ArtifactOut)
def get_artifact(artifact_id: str, db: DBSession = Depends(get_db)):
    row = db.get(models.Artifact, artifact_id)
    if not row:
        raise HTTPException(404, {"error": "Artifact not found", "code": "not_found"})
    return schemas.ArtifactOut(id=row.id, title=row.title, kind=row.kind, content=row.content, created_at=_iso(row.created_at))


@router.get("/settings/models")
def model_settings():
    return {**available_models(), "index_path": get_settings().INDEX_PATH}
