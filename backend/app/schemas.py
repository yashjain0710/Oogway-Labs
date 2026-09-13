"""Pydantic request/response contracts."""
from typing import Any, Literal
from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    title: str = Field(default="New chat", max_length=200)
    user_id: str = Field(default="local-user", max_length=100)


class SessionOut(BaseModel):
    id: str
    title: str
    user_id: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None, description="Omit to auto-create a session")
    message: str = Field(min_length=1, max_length=8000)
    top_k: int = Field(default=5, ge=1, le=10)


class SourceOut(BaseModel):
    source_id: str
    title: str
    url: str = ""
    chunk_index: int = 0
    score: float = 0.0
    excerpt: str = ""


class ChatResponse(BaseModel):
    session_id: str
    route: str
    answer: str
    sources: list[SourceOut]
    model: str
    provider: str
    artifact_id: str | None = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    route: str = "chat"
    sources: list[SourceOut] = []
    created_at: str


class ArtifactCreate(BaseModel):
    session_id: str | None = None
    title: str = Field(default="Untitled artifact", max_length=200)
    kind: Literal["markdown", "html"] = "markdown"
    prompt: str = Field(min_length=1, max_length=4000, description="What to generate")


class ArtifactOut(BaseModel):
    id: str
    title: str
    kind: str
    content: str
    created_at: str


class ErrorOut(BaseModel):
    error: str
    code: str
    detail: Any = None


class HealthOut(BaseModel):
    status: str
    database: str
    ollama: str
    provider: str
    model: str
    transcripts_indexed: int = 0
