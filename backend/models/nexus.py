"""Modelos Pydantic do NEXUS — espelhados à mão em frontend/src/lib/nexus.ts."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class BriefingCard(BaseModel):
    type: str  # clima | agenda | emails | noticias | saude
    title: str
    content: str


class BriefingResponse(BaseModel):
    id: str
    created_at: datetime
    speech: str
    full_text: str
    cards: list[BriefingCard] = Field(default_factory=list)
    face_verified: bool
    source: str  # gemini | local
    context: dict[str, Any] = Field(default_factory=dict)


class FaceVerifyResponse(BaseModel):
    verified: bool
    detail: str


class ChatResponse(BaseModel):
    id: str
    created_at: datetime
    reply: str
    cards: list[BriefingCard] = Field(default_factory=list)
    source: str  # gemini | local


class MemoryEvent(BaseModel):
    id: str
    kind: str  # briefing | user | nexus
    text: str
    created_at: datetime
    source: Optional[str] = None
    cards: list[BriefingCard] = Field(default_factory=list)