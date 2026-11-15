"""API de scoring comparatif des rotations candidates."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.core.dependencies import get_current_user, get_db
from app.models.parcelle import Parcelle
from app.schemas.rotation_scoring import RotationScoringRequest
from app.engine.rotation.scoring_engine import rank_rotations

router = APIRouter(prefix="/rotation", tags=["Rotation - Scoring agronomique"])


@router.post("/parcelles/{parcelle_id}/scoring")
def scorer_rotations(
    parcelle_id: int,
    payload: RotationScoringRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Classe les rotations à partir de six sous-scores normalisés fournis.

    Cette route ne lance pas les calculs satellite/sol/climat : elle agrège
    les sous-scores disponibles, conserve les preuves et signale les manques.
    """
    parcel = db.scalar(
        select(Parcelle).where(
            Parcelle.id == parcelle_id,
            Parcelle.farmer_id == current_user.id,
        )
    )
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcelle introuvable.")

    weights = payload.ponderations.model_dump()
    results = rank_rotations(
        [item.model_dump() for item in payload.rotations],
        weights,
        payload.minimum_dimensions_requises,
    )
    return {
        "parcelle_id": parcelle_id,
        "methode": "moyenne_ponderee_renormalisee_sur_dimensions_disponibles",
        "ponderations": weights,
        "rotations_classees": results,
        "notice": (
            "Les sous-scores doivent être calculés en amont et justifiés par des preuves. "
            "Aucune donnée absente n'est remplacée par zéro. Ce score agrégé ne remplace "
            "pas les sept règles d'exclusion ni une validation agronomique."
        ),
    }
