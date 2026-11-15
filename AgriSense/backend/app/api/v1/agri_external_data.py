from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Any
import base64
import csv, io, json
from datetime import date, datetime, time
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from zipfile import BadZipFile, ZipFile
from app.core.dependencies import get_current_user
from app.integrations.agri_external_data_collector.sources import SOURCES, source_metadata
from app.integrations.agri_external_data_collector.collector import (
    collect_source, list_datasets, get_dataset, import_records, validate_dataset, pipeline_status
)

router = APIRouter(prefix="/agri-external-data", tags=["Agriculture - Données externes"])


def _parse_upload_records(filename: str, raw: bytes) -> tuple[list[dict], Any]:
    name = filename.lower()
    if name.endswith(".json"):
        obj = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(obj, (list, dict)):
            raise ValueError("Le JSON doit être une liste ou un objet contenant records.")
        records = obj if isinstance(obj, list) else obj.get("records", [])
    elif name.endswith(".csv"):
        text = raw.decode("utf-8-sig")
        records = list(csv.DictReader(io.StringIO(text, newline="")))
    elif name.endswith(".xlsx"):
        try:
            with ZipFile(io.BytesIO(raw)) as archive:
                if sum(member.file_size for member in archive.infolist()) > 100 * 1024 * 1024:
                    raise ValueError("Le classeur Excel décompressé dépasse la limite de sécurité.")
            workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True, keep_links=False)
        except (BadZipFile, InvalidFileException, OSError) as exc:
            raise ValueError("Le fichier XLSX est invalide.") from exc
        try:
            worksheet = workbook.active
            rows = worksheet.iter_rows(values_only=True)
            headers_row = next(rows, None)
            if not headers_row:
                raise ValueError("Le classeur Excel est vide.")
            headers = [str(value).strip() if value is not None else "" for value in headers_row]
            if not all(headers) or len(headers) != len(set(headers)):
                raise ValueError("La première ligne Excel doit contenir des en-têtes non vides et uniques.")
            records = []
            for row in rows:
                if not any(value is not None for value in row):
                    continue
                if len(row) > len(headers) and any(value is not None for value in row[len(headers):]):
                    raise ValueError("Une ligne Excel contient des valeurs sans en-tête.")
                record = {}
                for header, value in zip(headers, row):
                    if isinstance(value, (datetime, date, time)):
                        value = value.isoformat()
                    record[header] = value
                records.append(record)
        finally:
            workbook.close()
    else:
        raise ValueError("Formats acceptés: CSV, XLSX ou JSON.")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("Le fichier doit contenir une liste d'objets / lignes tabulaires")
    raw_payload = {
        "filename": filename,
        "content_base64": base64.b64encode(raw).decode("ascii"),
    }
    return records, raw_payload


class DatasetValidationRequest(BaseModel):
    confirmed: bool
    notes: str | None = Field(default=None, max_length=2000)

class CollectRequest(BaseModel):
    indicators: list[str] | None = Field(default=None, max_length=12)
    params: dict[str, str] | None = None
    timeout: float = Field(default=30, ge=5, le=90)

@router.get("/pipeline/status")
def get_pipeline_status(_user=Depends(get_current_user)):
    try:
        return pipeline_status()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Base de données indisponible ou migration 007 manquante: {exc}")

@router.get("/sources")
def sources(_user=Depends(get_current_user)):
    return {"total":len(SOURCES),"sources":[{"id":k,**source_metadata(k)} for k in SOURCES]}

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
        raise HTTPException(status_code=502, detail=f"Collecte échouée (source externe ou persistance MySQL): {exc}")

@router.get("/datasets")
def datasets(_user=Depends(get_current_user)):
    try:
        rows=list_datasets()
        return {"total":len(rows),"datasets":rows}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Lecture MySQL impossible: {exc}")

@router.get("/datasets/{dataset_id}")
def dataset(dataset_id: str, _user=Depends(get_current_user)):
    try:
        result=get_dataset(dataset_id)
        if result is None: raise HTTPException(status_code=404, detail="Dataset introuvable")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Lecture MySQL impossible: {exc}")

@router.post("/import")
async def import_file(source_id: str = Form(...), file: UploadFile = File(...), observed_at: str | None = Form(default=None), _user=Depends(get_current_user)):
    if source_id not in SOURCES: raise HTTPException(status_code=404, detail="Source inconnue")
    raw=await file.read()
    if len(raw)>15*1024*1024: raise HTTPException(status_code=413, detail="Fichier limité à 15 Mo")
    try:
        records, raw_payload = _parse_upload_records(file.filename or "upload", raw)
        return import_records(
            source_id, records, file.filename or "upload", observed_at, raw_payload
        )
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
