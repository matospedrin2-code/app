"""Briefing matinal do NEXUS — coleta prévia + memória + Gemini 2.5 Flash."""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from pydantic import BaseModel
from pymongo import DESCENDING

from lib import feeds, nexus
from lib.db import db
from lib.memory import as_utc, memory_text
from models.nexus import BriefingCard, BriefingResponse

logger = logging.getLogger(__name__)
router = APIRouter()

WEEKDAYS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado", "domingo"]


class BriefingRequest(BaseModel):
    face_verified: bool = False


def _local_now() -> datetime:
    return datetime.now(ZoneInfo(os.environ.get("APP_TZ", "UTC")))


def _local_stamp(now: datetime) -> str:
    return f"{now:%d/%m/%Y}, {WEEKDAYS[now.weekday()]}, {now:%H:%M}"


def _response(doc: dict[str, Any]) -> BriefingResponse:
    return BriefingResponse(
        id=doc["id"],
        created_at=as_utc(doc.get("created_at")),
        speech=doc.get("speech", ""),
        full_text=doc.get("full_text", ""),
        cards=[BriefingCard(**c) for c in (doc.get("cards") or [])],
        face_verified=bool(doc.get("face_verified")),
        source=doc.get("source", "local"),
        context=doc.get("context") or {},
    )


@router.post("/briefing", response_model=BriefingResponse)
async def create_briefing(input: BriefingRequest) -> BriefingResponse:
    """Coleta clima/finanças/RSS, injeta a memória e gera o briefing com tags [CARD_*]."""
    data = await feeds.collect_all()
    memory = await memory_text()
    stamp = _local_stamp(_local_now())
    result = await nexus.generate_briefing(data, memory, input.face_verified, stamp)

    doc = {
        "id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc),
        "speech": result["speech"],
        "full_text": result["full_text"],
        "cards": result["cards"],
        "face_verified": input.face_verified,
        "source": result["source"],
        "context": data,
    }
    await db.briefings.insert_one(doc.copy())
    return _response(doc)


@router.get("/briefing/latest", response_model=Optional[BriefingResponse])
async def latest_briefing() -> Optional[BriefingResponse]:
    """Último briefing emitido — o HUD reidrata o estado anterior ao fechar o app."""
    doc = await db.briefings.find_one(sort=[("created_at", DESCENDING)])
    return _response(doc) if doc else None