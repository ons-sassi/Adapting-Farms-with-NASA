from fastapi import APIRouter, HTTPException
from app.schemas.rotation_ponderation import WeightedScoringRequest
from app.engine.rotation.priority_weighting import calculate_weighted_score

router = APIRouter(prefix="/rotation", tags=["Rotation - Pondération et score global"])

@router.post("/ponderation/calculer", summary="Calculer le score global selon les priorités du fermier")
def calculer_ponderation(payload: WeightedScoringRequest):
    try:
        return calculate_weighted_score(
            payload.priorites.model_dump(),
            payload.sous_scores.model_dump(),
            payload.seuil_couverture,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
