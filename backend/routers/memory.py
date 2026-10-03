"""Linha do tempo da memória do NEXUS — briefings e conversa, unificados."""

import logging

from fastapi import APIRouter
from pymongo import DESCENDING

from lib.db import db
from lib.memory import as_utc
from models.nexus import BriefingCard, MemoryEvent

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/memory", response_model=list[MemoryEvent])
async def get_memory(limit: int = 60) -> list[MemoryEvent]:
    limit = max(1, min(limit, 200))
    briefings = await db.briefings.find().sort("created_at", DESCENDING).to_list(limit)
    interactions = await db.interactions.find().sort("created_at", DESCENDING).to_list(limit)

    events: list[MemoryEvent] = []
    for doc in briefings:
        events.append(MemoryEvent(
            id=doc.get("id", ""),
            kind="briefing",
            text=doc.get("speech", ""),
            created_at=as_utc(doc.get("created_at")),
            source=doc.get("source"),
            cards=[BriefingCard(**c) for c in (doc.get("cards") or [])],
        ))
    for doc in interactions:
        events.append(MemoryEvent(
            id=doc.get("id", ""),
            kind="user" if doc.get("role") == "user" else "nexus",
            text=doc.get("text", ""),
            created_at=as_utc(doc.get("created_at")),
        ))
    events.sort(key=lambda e: e.created_at, reverse=True)
    return events[:limit]