from __future__ import annotations
import csv, io, json, os, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import httpx
from .sources import SOURCES

DATA_ROOT = Path(os.getenv("AGRI_EXTERNAL_DATA_DIR", "data/external_agri"))

def _json_safe(value):
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None: return value
    return str(value)

def _save(dataset: dict) -> dict:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    for sub in ("raw", "normalized"): (DATA_ROOT / sub).mkdir(parents=True, exist_ok=True)
    ident = dataset["dataset_id"]
    (DATA_ROOT / "raw" / f"{ident}.json").write_text(json.dumps(dataset["raw"], ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    normalized = {k:v for k,v in dataset.items() if k != "raw"}
    (DATA_ROOT / "normalized" / f"{ident}.json").write_text(json.dumps(normalized, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return normalized

def list_datasets() -> list[dict]:
    folder = DATA_ROOT / "normalized"
    if not folder.exists(): return []
    out=[]
    for p in sorted(folder.glob("*.json"), reverse=True):
        try: out.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError): continue
    return out

def get_dataset(dataset_id: str) -> dict | None:
    if not dataset_id.replace("-", "").isalnum(): return None
    p=DATA_ROOT / "normalized" / f"{dataset_id}.json"
    if not p.exists(): return None
    try: return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return None

def _world_bank(indicator: str, timeout: float) -> tuple[Any, str]:
    url=SOURCES["world_bank_tunisia_agriculture"]["url"].format(indicator=indicator)
    r=httpx.get(url, params={"format":"json", "per_page":100, "date":"2000:2026"}, timeout=timeout, follow_redirects=True)
    r.raise_for_status(); body=r.json()
    if not isinstance(body,list) or len(body)<2 or not isinstance(body[1],list):
        raise ValueError("Réponse World Bank inattendue")
    records=[]
    for row in body[1]:
        if row and row.get("value") is not None:
            records.append({"indicator_code":indicator,"indicator_name":(row.get("indicator") or {}).get("value"),
                "country":(row.get("country") or {}).get("value"),"year":row.get("date"),
                "value":row.get("value"),"unit":None,"source_record_id":row.get("countryiso3code")})
    return records, r.url.__str__()

def _faostat(params: dict, timeout: float) -> tuple[Any, str]:
    url=SOURCES["faostat_crop_production"]["url"]
    r=httpx.get(url, params=params, timeout=timeout, follow_redirects=True,
                headers={"User-Agent":"AgriExternalDataCollector/1.0 (research; contact project administrator)"})
    r.raise_for_status(); body=r.json()
    if not isinstance(body,dict): raise ValueError("Réponse FAOSTAT inattendue")
    records=body.get("data", body.get("items", []))
    if not isinstance(records,list): records=[]
    cleaned=[]
    for row in records:
        if isinstance(row,dict): cleaned.append({str(k):_json_safe(v) for k,v in row.items()})
    return cleaned, str(r.url)

def collect_source(source_id: str, indicators: list[str] | None=None, params: dict | None=None, timeout: float=30) -> dict:
    if source_id not in SOURCES: raise KeyError(source_id)
    source=SOURCES[source_id]
    if source["kind"] == "manual_reference":
        raise ValueError("Cette source nécessite un import documentaire contrôlé; aucun scraping automatique n'est configuré.")
    if source_id == "world_bank_tunisia_agriculture":
        codes=indicators or source["default_indicators"]
        if len(codes)>12: raise ValueError("Maximum 12 indicateurs par collecte")
        records=[]; request_urls=[]; errors=[]
        for code in codes:
            try:
                rows, used_url=_world_bank(code, timeout); records.extend(rows); request_urls.append(used_url)
            except Exception as exc: errors.append({"indicator":code,"error":str(exc)})
        if not records and errors: raise RuntimeError("Aucune série World Bank récupérée: " + "; ".join(e["error"] for e in errors))
        requested={"indicators":codes}
    elif source_id == "faostat_crop_production":
        requested={**source.get("default_params",{}), **(params or {})}
        records, used_url=_faostat(requested, timeout); request_urls=[used_url]; errors=[]
    else: raise ValueError("Type de source non pris en charge")
    now=datetime.now(timezone.utc).isoformat()
    dataset={"dataset_id":str(uuid.uuid4()),"source_id":source_id,"source_name":source["name"],
        "provider":source["provider"],"source_url":source["url"],"request_urls":request_urls,
        "retrieved_at":now,"requested_parameters":requested,"record_count":len(records),
        "quality_status":"needs_validation","geographic_scope":source.get("geography"),
        "temporal_scope":source.get("frequency"),"errors":errors,
        "data_notice":"Données externes brutes ou harmonisées minimalement; vérifier unité, définition, couverture, date et licence avant usage agronomique.",
        "records":records,"raw":records}
    return _save(dataset)

def import_records(source_id: str, records: list[dict], source_document: str, observed_at: str | None=None) -> dict:
    if source_id not in SOURCES: raise KeyError(source_id)
    if not records: raise ValueError("Le fichier importé ne contient aucune ligne")
    now=datetime.now(timezone.utc).isoformat(); ident=str(uuid.uuid4())
    dataset={"dataset_id":ident,"source_id":source_id,"source_name":SOURCES[source_id]["name"],
        "provider":SOURCES[source_id]["provider"],"source_url":SOURCES[source_id]["url"],
        "source_document":source_document,"retrieved_at":now,"observed_at":observed_at,
        "requested_parameters":{},"record_count":len(records),"quality_status":"needs_validation",
        "geographic_scope":SOURCES[source_id].get("geography"),"temporal_scope":SOURCES[source_id].get("frequency"),
        "errors":[],"data_notice":"Import manuel; origine et licence à contrôler. Pas encore validé pour calcul de rotation.",
        "records":records,"raw":records}
    return _save(dataset)


def validate_dataset(dataset_id: str, notes: str | None = None) -> dict | None:
    """Mark an external dataset as reviewed; keep an audit record in its metadata."""
    dataset = get_dataset(dataset_id)
    if dataset is None:
        return None
    dataset["quality_status"] = "validated"
    dataset["validation"] = {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "notes": (notes or "").strip() or None,
        "validated_by_user_action": True,
    }
    folder = DATA_ROOT / "normalized"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{dataset_id}.json"
    path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return dataset
