"""Authenticated endpoints for explaining precomputed agricultural results."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.schemas.explanation import (
    ExplanationHealth,
    ExplanationRequest,
    ExplanationResponse,
)
from app.services.llm.explanation_service import (
    ExplanationCategory,
    ExplanationServiceError,
    explain_results,
)

router = APIRouter(prefix="/explanations", tags=["Explanations (Groq)"])
API_ERRORS = {
    401: {"description": "Authentification requise ou invalide."},
    413: {"description": "Les résultats fournis dépassent la limite de taille."},
    422: {"description": "Requête ou réponse structurée invalide."},
    502: {"description": "Le fournisseur Groq est indisponible ou a renvoyé une réponse invalide."},
    503: {"description": "Groq n'est pas configuré ou a atteint sa limite."},
    504: {"description": "Délai d'attente Groq dépassé."},
}


async def _generate(
    payload: ExplanationRequest,
    category: ExplanationCategory,
) -> ExplanationResponse:
    try:
        return await explain_results(payload, category=category)
    except ExplanationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_detail) from None


@router.post(
    "/generate",
    response_model=ExplanationResponse,
    responses=API_ERRORS,
    summary="Expliquer des résultats agricoles calculés",
    description=(
        "Explique des résultats fournis par les moteurs déterministes. "
        "Groq ne calcule aucun score, ne modifie aucun classement et n'accède pas à la base."
    ),
)
async def generate_explanation(
    payload: ExplanationRequest,
    _current_user=Depends(get_current_user),
) -> ExplanationResponse:
    """Generate an explanation for already-computed results."""
    return await _generate(payload, "general")


@router.post(
    "/rotation",
    response_model=ExplanationResponse,
    responses=API_ERRORS,
    summary="Expliquer des stratégies de rotation",
    description="Explique les stratégies et compromis exactement à partir des résultats transmis.",
)
async def explain_rotation(
    payload: ExplanationRequest,
    _current_user=Depends(get_current_user),
) -> ExplanationResponse:
    return await _generate(payload, "rotation")


@router.post(
    "/scoring",
    response_model=ExplanationResponse,
    responses=API_ERRORS,
    summary="Expliquer les scores disponibles",
    description="Les scores absents sont signalés comme indisponibles, jamais recalculés.",
)
async def explain_scoring(
    payload: ExplanationRequest,
    _current_user=Depends(get_current_user),
) -> ExplanationResponse:
    return await _generate(payload, "scoring")


@router.post(
    "/risks",
    response_model=ExplanationResponse,
    responses=API_ERRORS,
    summary="Expliquer les risques et incertitudes",
    description="Distingue les faits, estimations, incertitudes et champs manquants reçus.",
)
async def explain_risks(
    payload: ExplanationRequest,
    _current_user=Depends(get_current_user),
) -> ExplanationResponse:
    return await _generate(payload, "risks")


@router.get(
    "/health",
    response_model=ExplanationHealth,
    summary="Vérifier la configuration Groq",
    description="Vérifie uniquement la présence de la clé côté serveur; aucun appel externe n'est effectué.",
)
async def explanation_health() -> ExplanationHealth:
    configured = bool(settings.groq_api_key)
    return ExplanationHealth(
        status="configured" if configured else "unconfigured",
        model=settings.groq_model,
        api_key_configured=configured,
    )
