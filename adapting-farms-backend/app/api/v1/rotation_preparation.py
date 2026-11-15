"""Audit des données disponibles avant calcul des sous-scores de rotation."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_current_user, get_db
from app.engine.rotation.data_readiness import audit_rotation_data
from app.models.indicateur import IndicateurCalculation
from app.models.parcelle import Parcelle
from app.models.sol import SoilAnalysis

router = APIRouter(prefix="/rotation", tags=["Rotation - Préparation des données"])


@router.get("/parcelles/{parcelle_id}/preparer-scoring")
def preparer_scoring_rotation(
    parcelle_id: int,
    history_limit: int = Query(default=30, ge=1, le=100),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Vérifie les données disponibles pour les six dimensions du scoring.

    L'endpoint ne crée aucun score artificiel et n'utilise que les données
    enregistrées pour la parcelle appartenant à l'utilisateur connecté.
    """
    parcel = db.scalar(
        select(Parcelle)
        .where(Parcelle.id == parcelle_id, Parcelle.farmer_id == current_user.id)
        .options(selectinload(Parcelle.cultures))
    )
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcelle introuvable.")

    soils = list(db.scalars(
        select(SoilAnalysis)
        .where(SoilAnalysis.parcelle_id == parcelle_id)
        .order_by(desc(SoilAnalysis.sampled_at), desc(SoilAnalysis.id))
    ).all())
    calculations = list(db.scalars(
        select(IndicateurCalculation)
        .where(
            IndicateurCalculation.parcelle_id == parcelle_id,
            IndicateurCalculation.farmer_id == current_user.id,
        )
        .order_by(desc(IndicateurCalculation.created_at), desc(IndicateurCalculation.id))
        .limit(history_limit)
    ).all())

    result = audit_rotation_data(parcel, soils, calculations)
    result.update({
        "parcelle": {"id": parcel.id, "nom": parcel.name, "surface_ha": parcel.area_ha},
        "methode": "audit_presence_donnees_sans_calcul_de_sous_score",
        "prochaine_etape": "Completer les observations manquantes, puis appliquer des formules de sous-scores documentees et validees.",
    })
    return result
