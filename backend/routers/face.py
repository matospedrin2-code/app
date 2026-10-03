"""Verificação facial — frame da webcam analisado pelo Gemini Vision."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from lib import nexus
from models.nexus import FaceVerifyResponse

logger = logging.getLogger(__name__)
router = APIRouter()


class FaceVerifyRequest(BaseModel):
    image: str = Field(min_length=32, description="Frame JPEG/PNG em data URL ou base64 puro")


@router.post("/face-verify", response_model=FaceVerifyResponse)
async def face_verify(input: FaceVerifyRequest) -> FaceVerifyResponse:
    """Nunca falha hard: indisponibilidade do núcleo vira verified=false com detalhe."""
    try:
        verified, detail = await nexus.verify_face(input.image)
        return FaceVerifyResponse(verified=verified, detail=detail)
    except Exception as exc:
        logger.warning("face-verify indisponível: %s", exc)
        return FaceVerifyResponse(
            verified=False,
            detail="Módulo biométrico momentaneamente indisponível — registre a frase de ativação manualmente, senhor.",
        )