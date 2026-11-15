"""
Étape 3 du chatbot : synthèse vocale ElevenLabs (seul moteur). Exécutée CÔTÉ SERVEUR : la clé n'atteint jamais le navigateur.
Variables d'environnement : ELEVENLABS_API_KEY (obligatoire), ELEVENLABS_VOICE_ID, ELEVENLABS_MODEL.
Modèles (doc ElevenLabs) : eleven_multilingual_v2 (qualité, défaut), eleven_flash_v2_5 (faible latence), eleven_v3 (expressif).
Tous gèrent l'arabe et le français ; aucun n'est dédié au derja tunisien : à tester avec votre voix.
"""
from __future__ import annotations

import os
import re

import requests

DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"       # voix d'exemple de la doc ElevenLabs : choisir la vôtre (ELEVENLABS_VOICE_ID)
DEFAULT_MODEL = "eleven_multilingual_v2"


class TTSNotConfigured(RuntimeError):
    """Clé ElevenLabs absente."""


class TTSError(RuntimeError):
    """Erreur renvoyée par ElevenLabs ou réseau."""


def clean_for_tts(text: str, max_chars: int = 1500) -> str:
    """Retire ce qu'une voix lirait mal : liens, markdown, emojis, espaces multiples."""
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[*_`#>~\[\]{}|]", " ", text)
    text = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:max_chars]


def synthesize(text: str, *, voice_id: str | None = None, model_id: str | None = None,
               timeout: float = 30, post=requests.post) -> bytes:
    """Texte -> octets MP3. `post` est injectable pour les tests."""
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise TTSNotConfigured("ELEVENLABS_API_KEY manquante")
    text = clean_for_tts(text)
    if not text:
        raise ValueError("texte vide après nettoyage")
    voice = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE)
    try:
        r = post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
                 params={"output_format": "mp3_44100_128"},
                 headers={"xi-api-key": key, "Content-Type": "application/json"},
                 json={"text": text, "model_id": model_id or os.environ.get("ELEVENLABS_MODEL", DEFAULT_MODEL)},
                 timeout=timeout)
    except requests.RequestException as e:
        raise TTSError(f"ElevenLabs injoignable : {type(e).__name__}") from e
    if r.status_code != 200:
        raise TTSError(f"ElevenLabs {r.status_code}")      # corps non relayé : peut contenir des détails de compte
    return r.content
