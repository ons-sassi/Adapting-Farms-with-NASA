"""API de génération des séquences pluriannuelles de rotation."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.dependencies import get_current_user, get_db
from app.models.parcelle import Parcelle
from app.schemas.rotation_generation import RotationGenerationRequest
from app.engine.rotation.exclusion_rules import evaluate_exclusion_rules
from app.engine.rotation.sequence_generator import generate_sequences

router = APIRouter(prefix="/rotation", tags=["Rotation - Génération des séquences"])

@router.post("/parcelles/{parcelle_id}/generer")
def generer_rotations(
    parcelle_id: int,
    payload: RotationGenerationRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Génère jusqu'à 3 séquences après les règles d'exclusion et transitions."""
    parcel = db.scalar(select(Parcelle).where(
        Parcelle.id == parcelle_id, Parcelle.farmer_id == current_user.id
    ))
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcelle introuvable.")

    from bd.cultures import get_culture
    candidates, candidate_errors = [], []
    for item in payload.candidates:
        try:
            crop = get_culture(item.identifiant)
            rule_payload = dict(item.rule_inputs)
            rule_payload["traits"] = item.traits
            evaluation = evaluate_exclusion_rules(crop, rule_payload)
            # calendar values supplied by the caller are explicit and versioned
            candidates.append({
                "name": crop.get("nom_scientifique") or crop.get("nom"),
                "code": crop.get("code"),
                "family": crop.get("famille"),
                "n_fixer": crop.get("n_fixer"),
                "root_depth_m": (crop.get("zr_mm") / 1000.0) if crop.get("zr_mm") is not None else None,
                "kc_ini": crop.get("kc_ini"),
                "rule_status": evaluation["statut_global"],
                "rule_reason": evaluation["interpretation"],
                "sowing_window_start": item.sowing_window_start,
                "sowing_window_end": item.sowing_window_end,
                "cycle_days": item.cycle_days,
                "underground_harvest": item.underground_harvest,
            })
        except (KeyError, ValueError) as exc:
            candidate_errors.append({"identifiant": item.identifiant, "error": str(exc)})
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Lecture catalogue impossible: {exc}") from exc

    result = generate_sequences(
        candidates=candidates,
        horizon=payload.horizon_years,
        start_date=payload.start_date,
        max_sequences=payload.max_sequences,
        sensitive_years=payload.sensitive_family_return_years,
        min_gap=payload.min_intercrop_days,
        initial_soc=payload.initial_soc_norm,
        initial_erosion=payload.initial_erosion_risk,
    )
    result.update({
        "parcelle_id": parcelle_id,
        "horizon_years": payload.horizon_years,
        "candidate_errors": candidate_errors,
        "calendar_notice": (
            "Les fenêtres de semis MM-DD et durées de cycle sont fournies dans la requête; "
            "elles doivent provenir d'une référence validée pour la parcelle et la variété."
        ),
        "engine_status": "sequence_generation",
    })
    return result
