"""SQLAlchemy models."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _uid() -> str:
    return str(uuid.uuid4())


class Session(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True, default=_uid)
    title = Column(String, default="New chat")
    user_id = Column(String, default="local-user")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, default=_uid)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role = Column(String)  # user | assistant
    content = Column(Text)
    sources_json = Column(Text, default="[]")
    route = Column(String, default="chat")
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    session = relationship("Session", back_populates="messages")


class TranscriptSource(Base):
    __tablename__ = "transcript_sources"
    id = Column(String, primary_key=True)  # filename slug
    title = Column(String)
    url = Column(String, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class TranscriptChunk(Base):
    __tablename__ = "transcript_chunks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String, ForeignKey("transcript_sources.id", ondelete="CASCADE"), index=True)
    chunk_index = Column(Integer, default=0)
    text = Column(Text)


class Artifact(Base):
    __tablename__ = "artifacts"
    id = Column(String, primary_key=True, default=_uid)
    session_id = Column(String, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, default="Untitled artifact")
    kind = Column(String, default="markdown")  # markdown | html
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
