"""API de comparaison et d'audit de confiance documentaire des rotations."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.core.dependencies import get_current_user, get_db
from app.models.parcelle import Parcelle
from app.schemas.rotation_comparaison import RotationComparisonRequest
from app.engine.rotation.comparison_engine import compare_rotations

router = APIRouter(prefix="/rotation", tags=["Rotation - Comparaison et confiance"])


@router.post("/parcelles/{parcelle_id}/comparer")
def comparer_rotations(
    parcelle_id: int,
    payload: RotationComparisonRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Compare au moins deux rotations et audite la couverture de leurs preuves."""
    parcel = db.scalar(select(Parcelle).where(
        Parcelle.id == parcelle_id,
        Parcelle.farmer_id == current_user.id,
    ))
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcelle introuvable.")

    result = compare_rotations(
        rotations=[item.model_dump(mode="python") for item in payload.rotations],
        weights=payload.ponderations.model_dump(),
        min_dimensions=payload.minimum_dimensions_requises,
        max_age_days=payload.fraicheur_max_jours,
    )
    result["parcelle_id"] = parcelle_id
    result["notice"] = (
        "La comparaison réutilise les sous-scores transmis. Elle n'exécute pas les calculs "
        "satellite, sol ou climat et ne remplace pas l'évaluation des règles d'exclusion."
    )
    return result
