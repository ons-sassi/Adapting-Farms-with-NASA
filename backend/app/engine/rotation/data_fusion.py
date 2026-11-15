"""Fusion déterministe, traçable et sans conversion implicite des sources."""
from __future__ import annotations
from datetime import date, datetime, timezone
from typing import Any

SOIL_FIELDS = {
    "ph", "organic_matter_percent", "texture", "nitrogen_mg_kg",
    "phosphorus_mg_kg", "potassium_mg_kg", "salinity_ds_m",
    "limestone_percent", "cec_cmol_kg",
}

# Rang élevé = source préférée. La fraîcheur départage seulement un même rang.
SOURCE_PRIORITY = {
    "farmer": 100, "manual": 100, "laboratory": 95,
    "local_station": 80, "regional": 70, "nasa_power": 65,
    "modis": 65, "landsat": 65, "sentinel": 65,
    "soilgrids": 50, "national": 40, "unknown": 10,
}
VALIDATED = {"validated", "verified", "approved"}


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, (date, datetime)) else (str(value) if value else None)


def _source_rank(source: str, field: str) -> int:
    key = source.strip().lower()
    if field in SOIL_FIELDS:
        if key in {"farmer", "manual"}: return 110
        if key in {"laboratory", "lab"}: return 105
        if key in {"soilgrids", "soil_grids"}: return 50
    aliases = {"nasa-power": "nasa_power", "nasa power": "nasa_power", "gee_modis": "modis"}
    key = aliases.get(key, key)
    return SOURCE_PRIORITY.get(key, 10)


def fuse_observations(observations: list[dict], parcel_values: dict | None = None,
                      soil_values: dict | None = None) -> dict:
    candidates: dict[str, list[dict]] = {}
    if parcel_values:
        observations = [{"source": "farmer", "domaine": "parcelle", "quality_status": "unverified",
                         "values": parcel_values, "units": {}, "observed_at": None,
                         "dataset_id": "parcelle_profile"}] + observations
    if soil_values:
        soil_observation = dict(soil_values)
        soil_source = soil_observation.pop("source", "manual")
        sampled_at = soil_observation.pop("sampled_at", None)
        quality_status = soil_observation.pop("quality_status", "unverified")
        observations = [{"source": soil_source, "domaine": "sol",
                         "quality_status": quality_status, "values": soil_observation,
                         "units": {}, "observed_at": sampled_at,
                         "dataset_id": "soil_analysis_db"}] + observations

    for obs_index, obs in enumerate(observations):
        source = str(obs.get("source") or "unknown").lower()
        quality = str(obs.get("quality_status") or "unverified").lower()
        for field, value in (obs.get("values") or {}).items():
            if value is None or value == "":
                continue
            observed = obs.get("observed_at")
            try:
                observed_dt = datetime.fromisoformat(str(observed).replace("Z", "+00:00")) if observed else None
                freshness = observed_dt.timestamp() if observed_dt else 0
            except (ValueError, TypeError, OSError):
                freshness = 0
            candidates.setdefault(field, []).append({
                "value": value, "source": source, "domaine": obs.get("domaine", "general"),
                "observed_at": _iso(observed), "retrieved_at": _iso(obs.get("retrieved_at")),
                "quality_status": quality, "validated": quality in VALIDATED,
                "unit": (obs.get("units") or {}).get(field), "dataset_id": obs.get("dataset_id"),
                "rank": _source_rank(source, field), "freshness": freshness,
                "input_index": obs_index,
            })

    merged, provenance, conflicts, missing = {}, {}, {}, []
    for field, items in candidates.items():
        # Validation outranks an unvalidated candidate at equal source priority.
        ordered = sorted(items, key=lambda x: (x["rank"], x["validated"], x["freshness"]), reverse=True)
        winner = ordered[0]
        merged[field] = winner["value"]
        provenance[field] = {k: winner[k] for k in (
            "source", "domaine", "observed_at", "retrieved_at", "quality_status", "unit", "dataset_id"
        )}
        distinct = {str(x["value"]) for x in items}
        if len(distinct) > 1:
            conflicts[field] = [{k: x[k] for k in ("value", "source", "unit", "quality_status", "observed_at")} for x in ordered]
    expected = sorted(SOIL_FIELDS | {"latitude", "longitude", "area_ha", "slope_percent"})
    missing = [field for field in expected if field not in merged]
    validated_count = sum(1 for x in provenance.values() if x["quality_status"] in VALIDATED)
    total = len(provenance)
    return {
        "donnees_fusionnees": merged,
        "provenance": provenance,
        "conflits_a_verifier": conflicts,
        "qualite": {
            "nombre_variables": total,
            "variables_validees": validated_count,
            "taux_validation_pct": round(100 * validated_count / total, 2) if total else 0.0,
            "variables_manquantes_recommandees": missing,
            "statut": "insuffisant" if not total else ("a_verifier" if conflicts or missing else "exploitable"),
        },
        "regles_priorite": {
            "sol": "mesure fermier/manuelle > laboratoire > SoilGrids",
            "autres": "priorité source configurée, validation puis fraîcheur",
            "unites": "aucune conversion automatique ; les unités sources sont conservées",
            "valeurs_manquantes": "jamais remplacées par zéro ni estimées",
        },
    }
