from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.core.dependencies import get_current_user, get_db
from app.integrations.agri_external_data_collector.collector import list_datasets
from app.models.indicateur import IndicateurCalculation
from app.models.parcelle import Parcelle
from app.models.sol import SoilAnalysis

router = APIRouter(prefix="/rotation", tags=["Rotation - Contexte des données"])


def _iso(value: Any):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _soil_dict(item: SoilAnalysis) -> dict:
    fields = (
        "id", "parcelle_id", "ph", "organic_matter_percent", "texture",
        "nitrogen_mg_kg", "phosphorus_mg_kg", "potassium_mg_kg",
        "salinity_ds_m", "limestone_percent", "cec_cmol_kg",
        "sampled_at", "source", "notes", "created_at", "updated_at",
    )
    return {field: _iso(getattr(item, field, None)) for field in fields}


def _indicator_dict(item: IndicateurCalculation | None):
    if item is None:
        return None
    return {
        "id": item.id,
        "culture": item.culture,
        "periode": {"start": item.start_date, "end": item.end_date},
        "status": item.status,
        "result": item.result,
        "created_at": _iso(item.created_at),
    }


@router.get("/parcelles/{parcelle_id}/context")
def get_rotation_context(
    parcelle_id: int,
    history_limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Assemble farmer, soil, indicator and validated external data for a parcel."""
    parcel = db.scalar(
        select(Parcelle)
        .where(Parcelle.id == parcelle_id, Parcelle.farmer_id == current_user.id)
        .options(selectinload(Parcelle.cultures), selectinload(Parcelle.constraints))
    )
    if parcel is None:
        raise HTTPException(status_code=404, detail="Parcelle introuvable")

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

    datasets = list_datasets()
    validated = [
        {
            "dataset_id": item.get("dataset_id"),
            "source_id": item.get("source_id"),
            "source_name": item.get("source_name"),
            "provider": item.get("provider"),
            "source_url": item.get("source_url"),
            "retrieved_at": item.get("retrieved_at"),
            "observed_at": item.get("observed_at"),
            "quality_status": item.get("quality_status"),
            "record_count": item.get("record_count"),
            "records": item.get("records", []),
            "validation": item.get("validation"),
        }
        for item in datasets if item.get("quality_status") == "validated"
    ]
    pending = [
        {
            "dataset_id": item.get("dataset_id"),
            "source_id": item.get("source_id"),
            "source_name": item.get("source_name"),
            "quality_status": item.get("quality_status"),
            "record_count": item.get("record_count"),
            "data_notice": item.get("data_notice"),
        }
        for item in datasets if item.get("quality_status") != "validated"
    ]

    return {
        "parcelle": {
            "id": parcel.id,
            "farmer_id": parcel.farmer_id,
            "name": parcel.name,
            "description": parcel.description,
            "area_ha": parcel.area_ha,
            "latitude": parcel.latitude,
            "longitude": parcel.longitude,
            "geometry": parcel.geometry,
            "irrigation_type": parcel.irrigation_type,
            "water_source": parcel.water_source,
            "slope_percent": parcel.slope_percent,
        },
        "farmer_data": {
            "crop_history": [
                {"id": c.id, "crop_name": c.crop_name, "season": c.season, "notes": c.notes}
                for c in parcel.cultures
            ],
            "constraints": [
                {"id": c.id, "constraint_type": c.constraint_type, "description": c.description}
                for c in parcel.constraints
            ],
        },
        "soil": {
            "latest": _soil_dict(soils[0]) if soils else None,
            "history": [_soil_dict(s) for s in soils],
        },
        "satellite_and_indicators": {
            "latest": _indicator_dict(calculations[0]) if calculations else None,
            "history": [_indicator_dict(c) for c in calculations],
            "notice": "Les résultats proviennent des calculs Indicateurs enregistrés; leur couverture dépend des sources et de la période du calcul.",
        },
        "external_agricultural_data": {
            "validated_datasets": validated,
            "pending_validation": pending,
            "notice": "Seuls les datasets validés sont inclus dans validated_datasets. Les datasets en attente ne doivent pas alimenter le moteur agronomique.",
        },
        "context_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "rotation_engine_status": "context_only",
            "message": "Cette API assemble les données; elle ne génère pas encore de rotation et ne calcule aucun score agronomique.",
        },
    }
