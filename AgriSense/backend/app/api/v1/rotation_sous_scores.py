"""API de calcul automatique des six sous-scores agronomiques."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.core.dependencies import get_current_user, get_db
from app.models.parcelle import Parcelle
from app.schemas.rotation_sous_scores import RotationSubscoreRequest
from app.engine.rotation.subscore_engine import calculate_rotation_subscores

router = APIRouter(prefix="/rotation", tags=["Rotation - Sous-scores agronomiques"])

@router.post("/parcelles/{parcelle_id}/sous-scores/calculer")
def calculer_sous_scores_rotation(
    parcelle_id: int,
    payload: RotationSubscoreRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Calcule les six sous-scores pour les cultures ayant PASS aux exclusions.

    Les données d'entrée sont des variables déjà collectées/normalisées par les
    connecteurs et le moteur de fusion. L'endpoint ne lance pas de requête satellite.
    """
    parcel = db.scalar(select(Parcelle).where(
        Parcelle.id == parcelle_id,
        Parcelle.farmer_id == current_user.id,
    ))
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcelle introuvable.")
    result = calculate_rotation_subscores(payload.model_dump())
    result["parcelle_id"] = parcelle_id
    result["parcelle"] = {"id": parcel.id, "nom": parcel.name, "surface_ha": parcel.area_ha}
    return result
