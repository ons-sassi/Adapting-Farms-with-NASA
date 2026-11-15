from __future__ import annotations

import json
import hashlib
import math
import os
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text

from app.core.config import PROJECT_ROOT
from app.db.session import engine
from .sources import SOURCES, source_readiness

_raw_root = Path(os.getenv("AGRI_EXTERNAL_DATA_DIR", "data/external_agri"))
DATA_ROOT = _raw_root if _raw_root.is_absolute() else PROJECT_ROOT / _raw_root


def _json_safe(value: Any) -> Any:
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        return value
    return str(value)


def _persist_dataset(dataset: dict) -> bool:
    """Persist a collected/imported dataset in MySQL; files are an auditable mirror."""
    metadata = {key: value for key, value in dataset.items() if key not in {"raw", "records"}}
    with engine.begin() as connection:
        result = connection.execute(
            text("""
                INSERT IGNORE INTO external_agri_datasets
                    (dataset_id, source_id, source_name, provider, quality_status,
                     retrieved_at, record_count, metadata_json, records_json, raw_json)
                VALUES
                    (:dataset_id, :source_id, :source_name, :provider, :quality_status,
                     :retrieved_at, :record_count, :metadata_json,
                     :records_json, :raw_json)
            """),
            {
                "dataset_id": dataset["dataset_id"],
                "source_id": dataset["source_id"],
                "source_name": dataset["source_name"],
                "provider": dataset["provider"],
                "quality_status": dataset["quality_status"],
                "retrieved_at": datetime.fromisoformat(dataset["retrieved_at"].replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None),
                "record_count": dataset["record_count"],
                "metadata_json": json.dumps(metadata, ensure_ascii=False, default=str),
                "records_json": json.dumps(dataset.get("records", []), ensure_ascii=False, default=str),
                "raw_json": json.dumps(dataset.get("raw", []), ensure_ascii=False, default=str),
            },
        )
    return result.rowcount == 1


def _decode_json(value):
    return json.loads(value) if isinstance(value, str) else value


def _records_fingerprint(source_id: str, records: list[dict]) -> str:
    canonical_records = sorted(
        json.dumps(
            {key: value for key, value in record.items() if key != "provenance"},
            sort_keys=True, ensure_ascii=False, default=str,
        )
        for record in records
    )
    serialized = json.dumps([source_id, canonical_records], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _existing_duplicate(dataset: dict) -> dict | None:
    fingerprint = dataset["content_fingerprint"]
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT metadata_json, records_json, raw_json
            FROM external_agri_datasets WHERE source_id = :source_id
        """), {"source_id": dataset["source_id"]}).mappings().all()
    for row in rows:
        metadata = _decode_json(row["metadata_json"])
        records = _decode_json(row["records_json"])
        existing_fingerprint = metadata.get("content_fingerprint")
        if not existing_fingerprint:
            existing_fingerprint = _records_fingerprint(dataset["source_id"], records or [])
        if existing_fingerprint == fingerprint:
            existing = {
                **metadata,
                "records": records,
                "raw": _decode_json(row["raw_json"]),
                "duplicate_detected": True,
            }
            existing["duplicate_of"] = existing.get("dataset_id")
            return existing
    return None


def _write_dataset_files(dataset: dict) -> dict:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    for sub in ("raw", "normalized"):
        (DATA_ROOT / sub).mkdir(parents=True, exist_ok=True)
    ident = dataset["dataset_id"]
    (DATA_ROOT / "raw" / f"{ident}.json").write_text(
        json.dumps(dataset.get("raw", []), ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    normalized = {key: value for key, value in dataset.items() if key != "raw"}
    (DATA_ROOT / "normalized" / f"{ident}.json").write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return normalized


def _save(dataset: dict) -> dict:
    dataset["content_fingerprint"] = _records_fingerprint(
        dataset["source_id"], dataset.get("records", [])
    )
    duplicate = _existing_duplicate(dataset)
    if duplicate is not None:
        return duplicate
    # MySQL is the system of record. Do not report success or write files if it fails.
    if not _persist_dataset(dataset):
        existing = get_dataset(dataset["dataset_id"])
        if existing is None:
            raise RuntimeError("Le dataset n'a pas été inséré et aucun dataset existant n'a été retrouvé.")
        existing["duplicate_detected"] = True
        existing["duplicate_of"] = existing.get("dataset_id")
        return existing
    return _write_dataset_files(dataset)


def list_datasets() -> list[dict]:
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT metadata_json, records_json
            FROM external_agri_datasets
            ORDER BY retrieved_at DESC, dataset_id DESC
        """)).mappings().all()
    datasets = []
    for row in rows:
        metadata = row["metadata_json"]
        records = row["records_json"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        if isinstance(records, str):
            records = json.loads(records)
        datasets.append({**metadata, "records": records})
    return datasets


def get_dataset(dataset_id: str) -> dict | None:
    if not dataset_id.replace("-", "").isalnum():
        return None
    with engine.connect() as connection:
        row = connection.execute(text("""
            SELECT metadata_json, records_json, raw_json
            FROM external_agri_datasets WHERE dataset_id = :dataset_id
        """), {"dataset_id": dataset_id}).mappings().first()
    if row is None:
        return None
    def decode(value):
        return json.loads(value) if isinstance(value, str) else value
    return {**decode(row["metadata_json"]), "records": decode(row["records_json"]), "raw": decode(row["raw_json"])}


def _world_bank_params(params: dict) -> dict:
    allowed = {"date", "page", "per_page"}
    unsupported = sorted(set(params) - allowed)
    if unsupported:
        raise ValueError(
            "Paramètres World Bank non pris en charge: " + ", ".join(unsupported)
            + ". Paramètres acceptés: date, page, per_page."
        )

    normalized = {"date": "2000:2026", "per_page": 100, "page": 1}
    if "date" in params:
        date_range = str(params["date"])
        match = re.fullmatch(r"(\d{4})(?::(\d{4}))?", date_range)
        if not match:
            raise ValueError("Le paramètre World Bank date doit être une année AAAA ou une plage AAAA:AAAA.")
        if match.group(2) and int(match.group(1)) > int(match.group(2)):
            raise ValueError("La plage World Bank date doit être croissante.")
        normalized["date"] = date_range
    for key in ("page", "per_page"):
        if key in params:
            try:
                value = int(params[key])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Le paramètre World Bank {key} doit être un entier positif.") from exc
            maximum = 1000 if key == "per_page" else None
            if value < 1 or (maximum and value > maximum):
                limit = "entre 1 et 1000" if maximum else "supérieur ou égal à 1"
                raise ValueError(f"Le paramètre World Bank {key} doit être {limit}.")
            normalized[key] = value
    return normalized


def _world_bank(indicator: str, timeout: float, params: dict | None = None) -> tuple[list[dict], str, Any]:
    url = SOURCES["world_bank_tunisia_agriculture"]["url"].format(indicator=indicator)
    request_params = {"format": "json", **_world_bank_params(params or {})}
    response = httpx.get(url, params=request_params, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, list) or len(body) < 2 or not isinstance(body[1], list):
        raise ValueError("Réponse World Bank inattendue")
    records = []
    for row in body[1]:
        if row and row.get("value") is not None:
            records.append({
                "indicator_code": indicator,
                "indicator_name": (row.get("indicator") or {}).get("value"),
                "country": (row.get("country") or {}).get("value"),
                "date": row.get("date"), "year": row.get("date"),
                "value": row.get("value"),
                "unit": (row.get("indicator") or {}).get("unit") or None,
                "geography": {"country_code": row.get("countryiso3code")},
                "data_semantics": "national_statistic",
                "quality_evidence": {
                    "provider_value_present": row.get("value") is not None,
                    "source_record_id": row.get("countryiso3code"),
                },
                "source_record_id": row.get("countryiso3code"),
            })
    return records, str(response.url), body


def _faostat(params: dict, timeout: float) -> tuple[list[dict], str, Any]:
    url = SOURCES["faostat_crop_production"]["url"]
    response = httpx.get(
        url, params=params, timeout=timeout, follow_redirects=True,
        headers={"User-Agent": "AgriExternalDataCollector/1.0 (research; contact project administrator)"},
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        raise ValueError("Réponse FAOSTAT inattendue")
    records = body.get("data", body.get("items", []))
    if not isinstance(records, list):
        records = []
    normalized = []
    for row in records:
        if not isinstance(row, dict):
            continue
        item = {str(key): _json_safe(value) for key, value in row.items()}
        year = item.get("Year") or item.get("year")
        item.update({
            "date": str(year) if year is not None else None,
            "year": year,
            "unit": item.get("Unit") or item.get("unit"),
            "geography": {
                "area": item.get("Area") or item.get("area"),
                "area_code": item.get("Area Code (M49)") or item.get("Area Code") or item.get("area_code"),
            },
            "data_semantics": "national_statistic",
            "quality_evidence": {
                "year_present": year is not None,
                "unit_present": bool(item.get("Unit") or item.get("unit")),
            },
        })
        normalized.append(item)
    return normalized, str(response.url), body


def _parse_iso_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} doit être une date ISO AAAA-MM-JJ.") from exc


def _power(params: dict, timeout: float) -> tuple[list[dict], str, Any]:
    try:
        latitude = float(params["latitude"])
        longitude = float(params["longitude"])
        start = str(params["start"])
        end = str(params["end"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("NASA POWER requiert latitude, longitude, start et end.") from exc
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Coordonnées latitude/longitude hors limites.")
    if _parse_iso_date(start, "start") > _parse_iso_date(end, "end"):
        raise ValueError("start doit précéder ou égaler end.")
    parameters = params.get("parameters", "T2M_MAX,T2M_MIN,T2M,PRECTOTCORR")
    if isinstance(parameters, str):
        parameters = [item.strip() for item in parameters.split(",") if item.strip()]
    if not isinstance(parameters, list) or not parameters:
        raise ValueError("parameters doit contenir au moins un paramètre NASA POWER.")
    parameters = [str(item) for item in parameters]
    request_params = {
        "parameters": ",".join(parameters), "community": "AG",
        "longitude": longitude, "latitude": latitude,
        "start": start.replace("-", ""), "end": end.replace("-", ""), "format": "JSON",
    }
    response = httpx.get(SOURCES["nasa_power_point"]["url"], params=request_params, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    body = response.json()
    properties = body.get("properties") if isinstance(body, dict) else None
    series = properties.get("parameter") if isinstance(properties, dict) else None
    if not isinstance(series, dict):
        raise ValueError("Réponse NASA POWER inattendue.")
    metadata = body.get("parameters") or {}
    units = {
        key: (
            (metadata.get(key) or {}).get("units")
            if isinstance(metadata.get(key), dict)
            else metadata.get(key)
        )
        for key in series
    }
    dates = sorted({str(day) for values in series.values() if isinstance(values, dict) for day in values})
    records = []
    for day in dates:
        values = {key: (series.get(key) or {}).get(day) for key in series}
        missing = [key for key, value in values.items() if value is None or value == -999]
        records.append({
            "date": datetime.strptime(day, "%Y%m%d").date().isoformat(),
            "coordinates": {"latitude": latitude, "longitude": longitude},
            "values": {key: None if value == -999 else value for key, value in values.items()},
            "units": units,
            "data_semantics": "modeled_estimate",
            "quality_evidence": {
                "provider": "NASA POWER", "missing_parameters": missing,
                "elevation_m": ((body.get("geometry") or {}).get("coordinates") or [None, None, None])[2],
            },
        })
    return records, str(response.url), body


def _soilgrids(params: dict, timeout: float) -> tuple[list[dict], str, Any]:
    try:
        latitude = float(params["latitude"])
        longitude = float(params["longitude"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("SoilGrids requiert latitude et longitude.") from exc
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("Coordonnées latitude/longitude hors limites.")
    properties = params.get("properties", "bdod,cec,cfvo,clay,nitrogen,phh2o,sand,silt,soc")
    depths = params.get("depths", "0-5cm,5-15cm,15-30cm,30-60cm,60-100cm,100-200cm")
    properties = [item.strip() for item in properties.split(",") if item.strip()] if isinstance(properties, str) else properties
    depths = [item.strip() for item in depths.split(",") if item.strip()] if isinstance(depths, str) else depths
    if (
        not isinstance(properties, list) or not isinstance(depths, list)
        or not properties or not depths
        or not all(isinstance(item, str) for item in properties + depths)
    ):
        raise ValueError("SoilGrids requiert des propriétés et profondeurs valides.")
    request_params = {
        "lat": latitude, "lon": longitude,
        # SoilGrids attend des paramètres répétés (property=clay&property=phh2o), pas une liste à virgules
        "property": properties, "depth": depths, "value": "mean",
    }
    response = httpx.get(
        SOURCES["soilgrids_profile"]["url"], params=request_params, timeout=timeout, follow_redirects=True
    )
    response.raise_for_status()
    body = response.json()
    layers = ((body.get("properties") or {}).get("layers") if isinstance(body, dict) else None)
    if not isinstance(layers, list):
        raise ValueError("Réponse SoilGrids inattendue.")
    values_by_depth: dict[str, dict] = {}
    raw_by_depth: dict[str, dict] = {}
    units, raw_units = {}, {}
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        name = layer.get("name")
        measure = layer.get("unit_measure") or {}
        # SoilGrids stocke des entiers (ex. phh2o=81 en "pH*10") : on divise par d_factor
        # pour obtenir l'unité cible (pH 8.1), comme common/connectors.fetch_soilgrids.
        factor = measure.get("d_factor") or 1
        if name:
            target = measure.get("target_units")
            if not target or target == "-":   # ex. phh2o : "pH*10" -> "pH"
                target = str(measure.get("mapped_units") or "").split("*")[0] or None
            units[name] = target
            raw_units[name] = measure.get("mapped_units")
        for depth in layer.get("depths", []):
            if isinstance(depth, dict) and depth.get("label"):
                mean = (depth.get("values") or {}).get("mean")
                raw_by_depth.setdefault(depth["label"], {})[name] = mean
                values_by_depth.setdefault(depth["label"], {})[name] = (
                    None if mean is None else round(mean / factor, 4)
                )
    records = [
        {
            "date": None,
            "coordinates": {"latitude": latitude, "longitude": longitude},
            "depth": depth,
            "values": values,
            "units": units,
            "values_raw": raw_by_depth.get(depth, {}),
            "units_raw": raw_units,
            "data_semantics": "interpolated_estimate",
            "quality_evidence": {
                "provider": "ISRIC SoilGrids", "spatial_resolution_m": 250,
                "present_properties": sorted(key for key, value in values.items() if value is not None),
            },
        }
        for depth, values in sorted(values_by_depth.items())
    ]
    return records, str(response.url), body


def _quality_evidence(source_id: str, records: list[dict]) -> dict:
    date_count = valid_date_count = invalid_date_count = 0
    coordinate_count = valid_coordinate_count = invalid_coordinate_count = 0
    for record in records:
        date_value = record.get("date")
        if date_value:
            date_count += 1
            try:
                date_text = str(date_value)
                if len(date_text) == 4 and date_text.isdigit():
                    if not 1 <= int(date_text) <= 9999:
                        raise ValueError
                else:
                    datetime.fromisoformat(date_text.replace("Z", "+00:00"))
                valid_date_count += 1
            except ValueError:
                invalid_date_count += 1
        coordinates = record.get("coordinates")
        if not coordinates and "latitude" in record and "longitude" in record:
            coordinates = {"latitude": record["latitude"], "longitude": record["longitude"]}
        if coordinates:
            coordinate_count += 1
            try:
                if isinstance(coordinates, dict):
                    latitude = float(coordinates.get("latitude", coordinates.get("lat")))
                    longitude = float(coordinates.get("longitude", coordinates.get("lon")))
                elif isinstance(coordinates, (list, tuple)) and len(coordinates) >= 2:
                    longitude, latitude = float(coordinates[0]), float(coordinates[1])
                else:
                    raise ValueError
                if not math.isfinite(latitude) or not math.isfinite(longitude):
                    raise ValueError
                if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                    raise ValueError
                valid_coordinate_count += 1
            except (TypeError, ValueError):
                invalid_coordinate_count += 1
    units_count = sum(
        bool(record.get("unit"))
        or (
            any(value for value in record.get("units", {}).values())
            if isinstance(record.get("units"), dict)
            else bool(record.get("units"))
        )
        for record in records
    )
    semantics = sorted({
        record.get("data_semantics", SOURCES[source_id].get("data_semantics", "unspecified"))
        for record in records
    })
    warnings = []
    if records and not date_count and source_id != "soilgrids_profile":
        warnings.append("Aucune date d'observation n'est présente dans les enregistrements.")
    if invalid_date_count:
        warnings.append(f"{invalid_date_count} date(s) ne respectent pas un format ISO valide.")
    if records and not coordinate_count and SOURCES[source_id].get("geography") == "Coordonnées ponctuelles":
        warnings.append("Aucune coordonnée n'est présente dans les enregistrements.")
    if invalid_coordinate_count:
        warnings.append(f"{invalid_coordinate_count} coordonnée(s) sont invalides ou hors limites.")
    if records and not units_count:
        warnings.append("Aucune unité n'est présente; vérifier avant interprétation agronomique.")
    return {
        "record_count": len(records), "records_with_date": date_count,
        "valid_dates": valid_date_count, "invalid_dates": invalid_date_count,
        "records_with_coordinates": coordinate_count,
        "valid_coordinates": valid_coordinate_count,
        "invalid_coordinates": invalid_coordinate_count,
        "records_with_units": units_count,
        "data_semantics": semantics, "warnings": warnings,
        "raw_response_preserved_separately": True,
    }


def collect_source(source_id: str, indicators: list[str] | None = None, params: dict | None = None, timeout: float = 30) -> dict:
    if source_id not in SOURCES:
        raise KeyError(source_id)
    source = SOURCES[source_id]
    if source["kind"] == "manual_reference":
        raise ValueError("Cette source nécessite un import documentaire contrôlé; aucun scraping automatique n'est configuré.")
    if source["kind"] == "gee":
        _, reason = source_readiness(source_id)
        raise ValueError(reason or "Google Earth Engine n'est pas configuré.")
    raw_response = None
    params = params or {}
    if source_id == "world_bank_tunisia_agriculture":
        world_bank_params = _world_bank_params(params)
        codes = indicators or source["default_indicators"]
        if len(codes) > 12:
            raise ValueError("Maximum 12 indicateurs par collecte")
        records, request_urls, errors, raw_response = [], [], [], []
        for code in codes:
            try:
                rows, used_url, response_body = _world_bank(code, timeout, world_bank_params)
                records.extend(rows)
                request_urls.append(used_url)
                raw_response.append(response_body)
            except Exception as exc:
                errors.append({"indicator": code, "error": str(exc)})
        if not records and errors:
            raise RuntimeError("Aucune série World Bank récupérée: " + "; ".join(e["error"] for e in errors))
        requested = {"indicators": codes, "params": world_bank_params}
    elif source_id == "faostat_crop_production":
        requested = {**source.get("default_params", {}), **(params or {})}
        records, used_url, raw_response = _faostat(requested, timeout)
        request_urls, errors = [used_url], []
    elif source_id == "nasa_power_point":
        requested = dict(params)
        records, used_url, raw_response = _power(requested, timeout)
        request_urls, errors = [used_url], []
    elif source_id == "soilgrids_profile":
        requested = dict(params)
        records, used_url, raw_response = _soilgrids(requested, timeout)
        request_urls, errors = [used_url], []
    else:
        raise ValueError("Type de source non pris en charge")

    now = datetime.now(timezone.utc).isoformat()
    provenance = {
        "source_id": source_id, "provider": source["provider"],
        "source_url": source["url"], "retrieved_at": now,
        "license": source.get("license"), "retrieval_method": source["kind"],
    }
    for record in records:
        record.setdefault("provenance", provenance)
    dataset = {
        "dataset_id": str(uuid.uuid4()), "source_id": source_id, "source_name": source["name"],
        "provider": source["provider"], "source_url": source["url"], "request_urls": request_urls,
        "retrieved_at": now, "requested_parameters": requested,         "record_count": len(records),
        "quality_status": "needs_validation", "geographic_scope": source.get("geography"),
        "temporal_scope": source.get("frequency"), "errors": errors,
        "provenance": {**provenance, "request_urls": request_urls},
        "quality_evidence": _quality_evidence(source_id, records),
        "data_notice": "Données externes brutes ou harmonisées minimalement; vérifier unité, définition, couverture, date et licence avant usage agronomique.",
        "records": records, "raw": raw_response,
    }
    return _save(dataset)


def import_records(
    source_id: str,
    records: list[dict],
    source_document: str,
    observed_at: str | None = None,
    raw_payload: Any = None,
) -> dict:
    if source_id not in SOURCES:
        raise KeyError(source_id)
    if not records:
        raise ValueError("Le fichier importé ne contient aucune ligne")
    if observed_at:
        try:
            datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("observed_at doit être une date ISO valide.") from exc
    now, ident = datetime.now(timezone.utc).isoformat(), str(uuid.uuid4())
    provenance = {
        "provider": SOURCES[source_id]["provider"],
        "source_url": SOURCES[source_id]["url"],
        "source_document": source_document,
        "retrieved_at": now, "observed_at": observed_at,
        "license": SOURCES[source_id].get("license"),
        "retrieval_method": "controlled_import",
    }
    normalized_records = []
    for record in records:
        item = dict(record)
        item.setdefault("data_semantics", SOURCES[source_id].get("data_semantics", "unclassified_import"))
        item.setdefault("quality_evidence", {"imported_from": source_document})
        item.setdefault("provenance", provenance)
        normalized_records.append(item)
    dataset = {
        "dataset_id": ident, "source_id": source_id, "source_name": SOURCES[source_id]["name"],
        "provider": SOURCES[source_id]["provider"], "source_url": SOURCES[source_id]["url"],
        "source_document": source_document, "retrieved_at": now, "observed_at": observed_at,
        "provenance": provenance,
        "requested_parameters": {}, "record_count": len(records), "quality_status": "needs_validation",
        "geographic_scope": SOURCES[source_id].get("geography"), "temporal_scope": SOURCES[source_id].get("frequency"),
        "errors": [], "quality_evidence": _quality_evidence(source_id, normalized_records),
        "data_notice": "Import manuel; origine, mesure/estimation, dates/coordonnées, unités et licence à contrôler. Pas encore validé pour calcul de rotation.",
        "records": normalized_records, "raw": records if raw_payload is None else raw_payload,
    }
    return _save(dataset)


def validate_dataset(dataset_id: str, notes: str | None = None) -> dict | None:
    dataset = get_dataset(dataset_id)
    if dataset is None:
        return None
    validation = {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "notes": (notes or "").strip() or None,
        "validated_by_user_action": True,
        "quality_evidence": dataset.get("quality_evidence") or _quality_evidence(
            dataset["source_id"], dataset.get("records", [])
        ),
    }
    with engine.begin() as connection:
        connection.execute(text("""
            UPDATE external_agri_datasets
            SET quality_status='validated',
                metadata_json=JSON_SET(metadata_json, '$.quality_status', 'validated', '$.validation', JSON_EXTRACT(:validation, '$'))
            WHERE dataset_id=:dataset_id
        """), {"dataset_id": dataset_id, "validation": json.dumps(validation, ensure_ascii=False)})
    dataset["quality_status"] = "validated"
    dataset["validation"] = validation
    _write_dataset_files(dataset)
    return dataset



def sync_legacy_files_to_database() -> dict:
    """Import existing normalized/raw JSON files once; dataset IDs remain immutable."""
    normalized_dir = DATA_ROOT / "normalized"
    imported = skipped = failed = 0
    errors = []
    if not normalized_dir.exists():
        return {"imported": 0, "skipped": 0, "failed": 0, "errors": []}
    for path in sorted(normalized_dir.glob("*.json")):
        try:
            dataset = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(dataset, dict) or not dataset.get("dataset_id"):
                raise ValueError("Métadonnées dataset_id absentes")
            dataset["raw"] = []
            raw_path = DATA_ROOT / "raw" / path.name
            if raw_path.exists():
                dataset["raw"] = json.loads(raw_path.read_text(encoding="utf-8"))
            dataset.setdefault("records", dataset["raw"] if isinstance(dataset["raw"], list) else [])
            dataset.setdefault("quality_status", "needs_validation")
            dataset.setdefault("retrieved_at", datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat())
            dataset.setdefault("record_count", len(dataset.get("records", [])))
            dataset.setdefault("source_id", "legacy_import")
            dataset.setdefault("source_name", "Ancien dataset local")
            dataset.setdefault("provider", "Import local")
            if _persist_dataset(dataset):
                imported += 1
            else:
                skipped += 1
        except Exception as exc:
            failed += 1
            errors.append({"file": path.name, "error": str(exc)})
    return {"imported": imported, "skipped": skipped, "failed": failed, "errors": errors}


def pipeline_status() -> dict:
    with engine.connect() as connection:
        count = connection.execute(text("SELECT COUNT(*) FROM external_agri_datasets")).scalar_one()
        by_status = connection.execute(text("""
            SELECT quality_status, COUNT(*) AS total
            FROM external_agri_datasets GROUP BY quality_status
        """)).mappings().all()
    raw_count = len(list((DATA_ROOT / "raw").glob("*.json"))) if (DATA_ROOT / "raw").exists() else 0
    normalized_count = len(list((DATA_ROOT / "normalized").glob("*.json"))) if (DATA_ROOT / "normalized").exists() else 0
    gee_source_statuses = [
        {"id": key, "status": readiness, "reason": reason}
        for key, value in SOURCES.items() if value["kind"] == "gee"
        for readiness, reason in [source_readiness(key)]
    ]
    return {
        "database": "connected", "database_dataset_count": count,
        "datasets_by_quality_status": {row["quality_status"]: row["total"] for row in by_status},
        "filesystem": {"raw_files": raw_count, "normalized_files": normalized_count,
                       "data_root": str(DATA_ROOT)},
        "supported_automatic_sources": [key for key, value in SOURCES.items() if value["kind"] == "json_api"],
        "configuration_blocked_sources": [
            source for source in gee_source_statuses if source["status"] == "configuration_blocked"
        ],
        "collector_unavailable_sources": [
            source for source in gee_source_statuses if source["status"] == "collector_unavailable"
        ],
        "manual_import_sources": [key for key, value in SOURCES.items() if value["kind"] == "manual_reference"],
        "note": "Les jeux de données restent needs_validation jusqu'à une validation humaine; aucun calcul agronomique ne les consomme automatiquement.",
    }
