"""
Endpoints du chatbot. Étape 1 (sous-titrage direct) = page /live + /captions ; étape 2 = /message ; étape 3 (ElevenLabs) = /speak.
"""
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.chatbot.factory import ChatbotServices
from app.services.chatbot.tts import TTSError, TTSNotConfigured, synthesize

router = APIRouter()
LIVE_PAGE = Path(__file__).resolve().parents[2] / "services" / "chatbot" / "static" / "live.html"


# Dépendances réelles du backend : JWT obligatoire, session MySQL, chatbot construit une seule fois.
from app.core.config import settings as _settings
from app.core.dependencies import get_current_user, get_db  # noqa: E402


def get_chatbot() -> ChatbotServices:
    from app.services.chatbot.wiring import get_services
    if not _settings.groq_api_key:
        raise HTTPException(503, "Chatbot non configuré : ajoutez GROQ_API_KEY dans backend/.env.")
    return get_services()


# tts.py lit les variables d'environnement : on y recopie celles de backend/.env (sans écraser l'existant).
for _key, _value in (("ELEVENLABS_API_KEY", _settings.elevenlabs_api_key),
                     ("ELEVENLABS_VOICE_ID", _settings.elevenlabs_voice_id),
                     ("ELEVENLABS_MODEL", _settings.elevenlabs_model)):
    if _value:
        os.environ.setdefault(_key, _value)


class ChatRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    parcelle_id: int | None = None
    previous_crop: str | None = None
    water_limited: bool = False
    n_rate: float | None = Field(None, ge=0, le=1000)
    lang: str = Field("fr", pattern="^(fr|en)$")


class CaptionRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1500)


@router.get("/live", include_in_schema=False)
def live_page():
    """Page de sous-titrage direct (HTML statique, sans donnée : l'authentification est exigée par les appels API)."""
    return FileResponse(LIVE_PAGE, media_type="text/html; charset=utf-8")


@router.post("/captions")
def captions(req: CaptionRequest, bot: ChatbotServices = Depends(get_chatbot), user=Depends(get_current_user)):
    try:
        return {"en": bot.translate(req.text)}
    except Exception:
        raise HTTPException(502, "traduction indisponible")


@router.post("/message")
def message(req: ChatRequest, bot: ChatbotServices = Depends(get_chatbot),
            db=Depends(get_db), user=Depends(get_current_user)):
    try:
        return bot.orchestrator.handle(db, user, req.text, parcelle_id=req.parcelle_id, previous_crop=req.previous_crop,
                                       water_limited=req.water_limited, n_rate=req.n_rate, lang=req.lang)
    except HTTPException:
        raise
    except Exception as exc:  # LLM (compréhension) indisponible, quota Groq...
        raise HTTPException(502, f"Assistant indisponible ({type(exc).__name__}).") from exc


@router.post("/speak")
def speak(req: SpeakRequest, user=Depends(get_current_user)):
    try:
        audio = synthesize(req.text)
    except TTSNotConfigured:
        raise HTTPException(503, "synthèse vocale non configurée")
    except ValueError as e:
        raise HTTPException(422, str(e))
    except TTSError:
        raise HTTPException(502, "synthèse vocale indisponible")
    return Response(content=audio, media_type="audio/mpeg")
