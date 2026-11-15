"""Extraction générique d'un PDF ou d'une image vers un JSON (API Gemini).

Aucune structure imposée : le modèle renvoie tout ce qu'il trouve dans le document
(champs, tableaux, notes). Le mapping vers un schéma précis (ex. SoilLabInput) se fait ensuite.
"""
import json
import os

from google import genai
from google.genai import errors, types

from integrations.errors import ExternalSourceError
from settings import settings

SOURCE_NAME = "Gemini (extraction de document)"
TIMEOUT_MS = 90_000

SYSTEM_PROMPT = """Tu extrais les données d'un document (PDF ou image : rapport, analyse, tableau, formulaire, facture...).
Réponds UNIQUEMENT avec un objet JSON valide, de cette forme :
{
  "document_type": "...",
  "language": "fr",
  "title": null,
  "date": null,
  "fields": {"nom_du_champ": {"value": 7.8, "unit": null}},
  "tables": [{"name": "...", "columns": ["..."], "rows": [["..."]]}],
  "notes": []
}
Règles :
- Extrais toutes les données présentes. N'invente rien : valeur absente ou illisible = null.
- Les nombres sont de vrais nombres JSON (virgule décimale -> point : "7,8" devient 7.8). L'unité va dans "unit".
- Les noms de champs sont en snake_case, dans la langue du document (ne traduis pas).
- Les dates au format YYYY-MM-DD quand c'est possible.
- Les tableaux gardent l'ordre des lignes et des colonnes du document.
- "notes" : remarques, méthodes, signatures ou textes libres utiles."""


class UnsupportedDocumentError(ValueError):
    """Le fichier n'est ni un PDF ni une image acceptée par Gemini."""


def _mime_type(content: bytes) -> str:
    """Type détecté sur les premiers octets (le nom de fichier n'est pas fiable)."""
    if content.startswith(b"%PDF"):
        return "application/pdf"
    if content.startswith(b"\x89PNG"):
        return "image/png"
    if content.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    raise UnsupportedDocumentError("Formats acceptés : PDF, PNG, JPEG, WEBP.")


def _parse_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ExternalSourceError(SOURCE_NAME, "réponse non JSON")
    try:
        return json.loads(text[start : end + 1])
    except ValueError as exc:
        raise ExternalSourceError(SOURCE_NAME, "JSON invalide dans la réponse") from exc


def extract_document(content: bytes) -> dict:
    mime = _mime_type(content)
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ExternalSourceError(SOURCE_NAME, "clé API manquante (définir AGRISENSE_GEMINI_API_KEY dans .env)")
    try:
        client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=TIMEOUT_MS))
        response = client.models.generate_content(
            model=settings.extractor_model,
            contents=[
                types.Part.from_bytes(data=content, mime_type=mime),
                "Extrais toutes les données de ce document en JSON.",
            ],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0,
                max_output_tokens=16000,
            ),
        )
    except errors.APIError as exc:
        # 429 = quota gratuit atteint, 404 = nom de modèle inconnu, 400/403 = clé ou requête refusée
        raise ExternalSourceError(SOURCE_NAME, f"erreur {exc.code} avec le modèle {settings.extractor_model} : {exc.message}") from exc
    except Exception as exc:  # réseau coupé, timeout...
        raise ExternalSourceError(SOURCE_NAME, f"requête impossible ({exc.__class__.__name__})") from exc

    candidate = response.candidates[0] if response.candidates else None
    if candidate is not None and candidate.finish_reason == types.FinishReason.MAX_TOKENS:
        raise ExternalSourceError(SOURCE_NAME, "document trop dense, réponse tronquée")
    return _parse_json(response.text or "")
