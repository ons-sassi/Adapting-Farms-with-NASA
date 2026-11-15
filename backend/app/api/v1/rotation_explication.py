"""API d'explication textuelle des résultats de rotation avec Groq."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.core.dependencies import get_current_user, get_db
from app.models.parcelle import Parcelle
from app.schemas.rotation_explication import RotationExplanationRequest
from app.engine.rotation.groq_explainer import generer_explication

router = APIRouter(prefix="/rotation", tags=["Rotation - Explications IA (Groq)"])


@router.post("/parcelles/{parcelle_id}/expliquer")
async def expliquer_rotation(
    parcelle_id: int,
    payload: RotationExplanationRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Explique des résultats calculés en amont ; Groq ne réalise aucun calcul agronomique."""
    parcel = db.scalar(select(Parcelle).where(
        Parcelle.id == parcelle_id,
        Parcelle.farmer_id == current_user.id,
    ))
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcelle introuvable.")

    result = await generer_explication(
        donnees_rotation=payload.donnees_rotation,
        langue=payload.langue,
        niveau_detail=payload.niveau_detail,
    )
    result["parcelle_id"] = parcelle_id
    return result
