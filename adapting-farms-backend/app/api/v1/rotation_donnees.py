"""API de fusion, normalisation et audit des données de rotation."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from app.core.dependencies import get_current_user, get_db
from app.models.parcelle import Parcelle
from app.models.sol import SoilAnalysis
from app.schemas.rotation_donnees import RotationDataFusionRequest
from app.engine.rotation.data_fusion import fuse_observations

router = APIRouter(prefix="/rotation", tags=["Rotation - Fusion des données"])


@router.post("/parcelles/{parcelle_id}/donnees/fusionner")
def fusionner_donnees_rotation(
    parcelle_id: int,
    payload: RotationDataFusionRequest,
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Fusionne les observations fournies et les données fermier déjà en base.

    Les observations NASA POWER, SoilGrids, satellites et datasets externes sont
    transmises par le collecteur appelant ; cette route ne déclenche pas de requête externe.
    """
    parcel = db.scalar(select(Parcelle).where(
        Parcelle.id == parcelle_id, Parcelle.farmer_id == current_user.id
    ))
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcelle introuvable")

    parcel_values = None
    if payload.inclure_donnees_parcelle:
        parcel_values = {
            "latitude": parcel.latitude, "longitude": parcel.longitude,
            "area_ha": parcel.area_ha, "slope_percent": parcel.slope_percent,
            "irrigation_type": parcel.irrigation_type, "water_source": parcel.water_source,
        }
        parcel_values = {k: v for k, v in parcel_values.items() if v is not None}

    soil_values = None
    if payload.inclure_dernier_sol:
        soil = db.scalar(select(SoilAnalysis).where(
            SoilAnalysis.parcelle_id == parcelle_id
        ).order_by(desc(SoilAnalysis.sampled_at), desc(SoilAnalysis.id)).limit(1))
        if soil:
            soil_values = {
                "ph": soil.ph, "organic_matter_percent": soil.organic_matter_percent,
                "texture": soil.texture, "nitrogen_mg_kg": soil.nitrogen_mg_kg,
                "phosphorus_mg_kg": soil.phosphorus_mg_kg,
                "potassium_mg_kg": soil.potassium_mg_kg, "salinity_ds_m": soil.salinity_ds_m,
                "limestone_percent": soil.limestone_percent, "cec_cmol_kg": soil.cec_cmol_kg,
                "sampled_at": soil.sampled_at, "source": soil.source,
            }
            soil_values = {k: v for k, v in soil_values.items() if v is not None}

    observations = [item.model_dump(mode="json") for item in payload.observations]
    result = fuse_observations(observations, parcel_values, soil_values)
    result.update({"parcelle_id": parcelle_id, "parcelle_nom": parcel.name,
                   "mode": "fusion_sans_persistance", "observations_fournies": len(observations)})
    return result
