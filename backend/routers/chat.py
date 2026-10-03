"""Conversa de acompanhamento com o NEXUS — persona + memória persistente."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field
from pymongo import DESCENDING

from lib import nexus
from lib.db import db
from lib.memory import memory_text
from models.nexus import ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


@router.post("/chat", response_model=ChatResponse)
async def chat(input: ChatRequest) -> ChatResponse:
    """Cada mensagem do Senhor e cada resposta do NEXUS são gravadas no Mongo."""
    created = datetime.now(timezone.utc)
    _ = await db.interactions.insert_one({
        "id": str(uuid.uuid4()),
        "role": "user",
        "text": input.message.strip(),
        "created_at": created,
    })

    memory = await memory_text()
    # Contexto mais recente coletado — permite que follow-ups sobre clima/finanças/notícias usem dados reais.
    latest = await db.briefings.find_one(
        sort=[("created_at", DESCENDING)], projection={"context": 1}
    )
    context_block = nexus.format_context(latest["context"]) if latest and latest.get("context") else ""
    result = await nexus.chat_reply(input.message.strip(), memory, context_block)
    created_reply = datetime.now(timezone.utc)
    reply_id = str(uuid.uuid4())
    _ = await db.interactions.insert_one({
        "id": reply_id,
        "role": "nexus",
        "text": result["reply"],
        "created_at": created_reply,
    })
    return ChatResponse(
        id=reply_id,
        created_at=created_reply,
        reply=result["reply"],
        cards=result["cards"],
        source=result["source"],
    )