"""Endpoint du calculateur d'impact : utilisable sans chatbot (frontend, scripts, autres services)."""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.impact_service import ImpactService

router = APIRouter()
# Les identifiants du catalogue de l'interface (ble-dur, feve-feverole...) sont aussi acceptés.
_impact = ImpactService(id_map={"ble-dur": "wheat", "ble-tendre": "wheat", "feve-feverole": "fava"})


class ImpactRequest(BaseModel):
    sequence: list[str] = Field(..., min_length=1, description="rotation proposée, ex. ['fava','wheat']")
    baseline: list[str] | None = None            # défaut : même céréale chaque saison
    hectares: float = 1.0
    n_rate: float | None = None                  # dose d'azote réelle du fermier (kg N/ha) ; sinon valeur d'exemple signalée
    lang: str = "fr"


@router.post("/calculer")
def calculer_impact(req: ImpactRequest):
    return _impact.evaluate(req.sequence, hectares=req.hectares, n_rate=req.n_rate,
                            baseline=req.baseline, lang=req.lang)
