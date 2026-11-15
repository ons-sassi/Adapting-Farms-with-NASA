from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Any
import csv, io, json
from app.core.dependencies import get_current_user
from app.integrations.agri_external_data_collector.sources import SOURCES
from app.integrations.agri_external_data_collector.collector import (
    collect_source, list_datasets, get_dataset, import_records, validate_dataset
)

router = APIRouter(prefix="/agri-external-data", tags=["Agriculture - Données externes"])

class DatasetValidationRequest(BaseModel):
    confirmed: bool
    notes: str | None = Field(default=None, max_length=2000)

class CollectRequest(BaseModel):
    indicators: list[str] | None = Field(default=None, max_length=12)
    params: dict[str, str] | None = None
    timeout: float = Field(default=30, ge=5, le=90)

@router.get("/sources")
def sources(_user=Depends(get_current_user)):
    return {"total":len(SOURCES),"sources":[{"id":k,**v} for k,v in SOURCES.items()]}

@router.post("/collect/{source_id}")
def collect(source_id: str, data: CollectRequest | None = None, _user=Depends(get_current_user)):
    try:
        payload=data or CollectRequest()
        return collect_source(source_id, payload.indicators, payload.params, payload.timeout)
    except KeyError:
        raise HTTPException(status_code=404, detail="Source inconnue. Consulte GET /sources.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Collecte externe échouée: {exc}")

@router.get("/datasets")
def datasets(_user=Depends(get_current_user)):
    rows=list_datasets()
    return {"total":len(rows),"datasets":rows}

@router.get("/datasets/{dataset_id}")
def dataset(dataset_id: str, _user=Depends(get_current_user)):
    result=get_dataset(dataset_id)
    if result is None: raise HTTPException(status_code=404, detail="Dataset introuvable")
    return result

@router.post("/import")
async def import_file(source_id: str = Form(...), file: UploadFile = File(...), observed_at: str | None = Form(default=None), _user=Depends(get_current_user)):
    if source_id not in SOURCES: raise HTTPException(status_code=404, detail="Source inconnue")
    name=(file.filename or "upload").lower()
    raw=await file.read()
    if len(raw)>15*1024*1024: raise HTTPException(status_code=413, detail="Fichier limité à 15 Mo")
    try:
        if name.endswith(".json"):
            obj=json.loads(raw.decode("utf-8-sig")); records=obj if isinstance(obj,list) else obj.get("records", [])
        elif name.endswith(".csv"):
            text=raw.decode("utf-8-sig"); records=list(csv.DictReader(io.StringIO(text, newline="")))
        else: raise ValueError("Formats acceptés: CSV ou JSON. Convertis les XLSX en CSV avant import.")
        if not isinstance(records,list) or not all(isinstance(x,dict) for x in records): raise ValueError("Le fichier doit contenir une liste d'objets / lignes tabulaires")
        return import_records(source_id, records, file.filename or "upload", observed_at)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/datasets/{dataset_id}/validate")
def validate_external_dataset(
    dataset_id: str,
    data: DatasetValidationRequest,
    _user=Depends(get_current_user),
):
    if not data.confirmed:
        raise HTTPException(status_code=422, detail="La validation doit être explicitement confirmée.")
    result = validate_dataset(dataset_id, data.notes)
    if result is None:
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    return {
        "message": "Dataset marqué comme validé. Vérifiez que les unités, périodes, couverture et droits de réutilisation ont bien été contrôlés.",
        "dataset_id": dataset_id,
        "quality_status": result.get("quality_status"),
        "validation": result.get("validation"),
    }
