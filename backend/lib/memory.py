"""Memória persistente do NEXUS — tudo o que foi dito vive no Mongo."""

import logging
from datetime import datetime, timezone

from pymongo import DESCENDING

from lib.db import db

logger = logging.getLogger(__name__)


def as_utc(dt: datetime | None) -> datetime:
    """Motor devolve datetime naive; normaliza para UTC aware na leitura."""
    if dt is None:
        return datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def memory_text(limit_events: int = 14) -> str:
    """Resumo dos eventos mais recentes (briefings + conversa) para o contexto do Gemini."""
    try:
        briefings = await db.briefings.find({}, {"speech": 1, "created_at": 1}).sort("created_at", DESCENDING).to_list(4)
        interactions = await db.interactions.find({}, {"role": 1, "text": 1, "created_at": 1}).sort("created_at", DESCENDING).to_list(limit_events)
    except Exception as exc:
        logger.warning("leitura de memória falhou: %s", exc)
        return ""

    events: list[tuple[datetime, str]] = []
    for b in briefings:
        events.append((as_utc(b.get("created_at")), f"[BRIEFING] {(b.get('speech') or '')[:280]}"))
    for i in interactions:
        who = "SENHOR" if i.get("role") == "user" else "NEXUS"
        events.append((as_utc(i.get("created_at")), f"[{who}] {(i.get('text') or '')[:200]}"))
    events.sort(key=lambda e: e[0], reverse=True)
    return "\n".join(f"({t:%d/%m %H:%M} UTC) {txt}" for t, txt in events[:limit_events])