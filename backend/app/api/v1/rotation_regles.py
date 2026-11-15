"""Endpoint d'évaluation des 7 règles d'exclusion agronomique."""
from fastapi import APIRouter, Depends, HTTPException
from app.core.dependencies import get_current_user
from app.schemas.rotation_regles import ExclusionRuleEvaluationRequest
from app.engine.rotation.exclusion_rules import evaluate_exclusion_rules

router = APIRouter(prefix="/rotation/regles", tags=["Rotation - Règles d'exclusion"])

@router.post("/evaluer")
def evaluer_regles_exclusion(
    payload: ExclusionRuleEvaluationRequest,
    current_user=Depends(get_current_user),
):
    """Evalue une culture avec les observations explicitement fournies.

    Cette première version ne déclenche pas elle-même les collecteurs satellites.
    Les valeurs absentes produisent UNKNOWN et ne sont jamais inventées.
    """
    try:
        from bd.cultures import get_culture
        crop = get_culture(payload.culture_identifiant)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Catalogue cultures indisponible : {exc}") from exc

    data = payload.model_dump()
    result = evaluate_exclusion_rules(crop, data)
    result["culture_identifiant_demande"] = payload.culture_identifiant
    result["notice"] = (
        "Evaluation déterministe sur les observations fournies. "
        "PASS ne vaut pas recommandation finale; UNKNOWN interdit la validation automatique."
    )
    return result
