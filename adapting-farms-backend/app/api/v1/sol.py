import csv
import io
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.repositories import sol_repository
from app.schemas.sol import SoilAnalysisCreate, SoilAnalysisRead, SoilAnalysisUpdate
from app.services.sol_service import get_owned_analysis, get_owned_parcelle

router = APIRouter(prefix="/sol", tags=["Sol"])

CSV_COLUMNS = [
    "parcelle_id", "ph", "organic_matter_percent", "texture",
    "nitrogen_mg_kg", "phosphorus_mg_kg", "potassium_mg_kg",
    "salinity_ds_m", "limestone_percent", "cec_cmol_kg",
    "sampled_at", "source", "notes"
]
NUMERIC_FIELDS = {
    "ph", "organic_matter_percent", "nitrogen_mg_kg", "phosphorus_mg_kg",
    "potassium_mg_kg", "salinity_ds_m", "limestone_percent", "cec_cmol_kg"
}


def _farmer_id(user: Any) -> int:
    value = getattr(user, "id", None)
    if value is None:
        raise HTTPException(status_code=401, detail="Utilisateur non authentifié")
    return int(value)


def _parse_row(row: dict[str, Any]) -> dict[str, Any]:
    data = {}
    try:
        data["parcelle_id"] = int(row["parcelle_id"])
        if data["parcelle_id"] <= 0:
            raise ValueError("parcelle_id doit être positif")
        for field in NUMERIC_FIELDS:
            raw = row.get(field)
            data[field] = None if raw in (None, "") else float(raw)
        data["texture"] = row.get("texture") or None
        raw_date = row.get("sampled_at")
        data["sampled_at"] = date.fromisoformat(raw_date) if raw_date else None
        data["source"] = (row.get("source") or "manual").strip().lower()
        if data["source"] not in {"manual", "laboratory", "soilgrids"}:
            raise ValueError("source doit être manual, laboratory ou soilgrids")
        data["notes"] = row.get("notes") or None
        if data["ph"] is not None and not 0 <= data["ph"] <= 14:
            raise ValueError("ph doit être compris entre 0 et 14")
        if data["organic_matter_percent"] is not None and not 0 <= data["organic_matter_percent"] <= 100:
            raise ValueError("organic_matter_percent doit être compris entre 0 et 100")
        if data["limestone_percent"] is not None and not 0 <= data["limestone_percent"] <= 100:
            raise ValueError("limestone_percent doit être compris entre 0 et 100")
        for field in NUMERIC_FIELDS - {"ph", "organic_matter_percent", "limestone_percent"}:
            if data[field] is not None and data[field] < 0:
                raise ValueError(f"{field} doit être positif ou nul")
        return data
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"Ligne invalide: {exc}") from exc


@router.post("/", response_model=SoilAnalysisRead, status_code=status.HTTP_201_CREATED)
def create_soil_analysis(
    payload: SoilAnalysisCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not get_owned_parcelle(db, payload.parcelle_id, _farmer_id(current_user)):
        raise HTTPException(status_code=404, detail="Parcelle introuvable")
    return sol_repository.create(db, payload.model_dump())


@router.get("/parcelle/{parcelle_id}", response_model=list[SoilAnalysisRead])
def list_soil_analyses(
    parcelle_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not get_owned_parcelle(db, parcelle_id, _farmer_id(current_user)):
        raise HTTPException(status_code=404, detail="Parcelle introuvable")
    return sol_repository.list_for_parcelle(db, parcelle_id)


@router.get("/{analysis_id}", response_model=SoilAnalysisRead)
def read_soil_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    obj = get_owned_analysis(db, analysis_id, _farmer_id(current_user))
    if not obj:
        raise HTTPException(status_code=404, detail="Analyse introuvable")
    return obj


@router.put("/{analysis_id}", response_model=SoilAnalysisRead)
def update_soil_analysis(
    analysis_id: int,
    payload: SoilAnalysisUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    obj = get_owned_analysis(db, analysis_id, _farmer_id(current_user))
    if not obj:
        raise HTTPException(status_code=404, detail="Analyse introuvable")
    return sol_repository.update(db, obj, payload.model_dump(exclude_unset=True))


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_soil_analysis(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    obj = get_owned_analysis(db, analysis_id, _farmer_id(current_user))
    if not obj:
        raise HTTPException(status_code=404, detail="Analyse introuvable")
    sol_repository.delete(db, obj)
    return None


@router.get("/template")
def download_csv_template():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    writer.writerow([1, 7.2, 2.1, "limono-argileux", 35, 18, 140, 0.4, 5, 12, "2026-10-01", "laboratory", "Exemple à remplacer"])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="modele_analyses_sol.csv"'}
    )


async def _read_rows(file: UploadFile) -> list[dict[str, Any]]:
    content = await file.read()
    filename = (file.filename or "").lower()
    if filename.endswith(".csv"):
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Le fichier CSV doit être encodé en UTF-8")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or "parcelle_id" not in reader.fieldnames:
            raise HTTPException(status_code=400, detail="Colonne parcelle_id manquante")
        return list(reader)
    if filename.endswith((".xlsx", ".xlsm")):
        try:
            from openpyxl import load_workbook
        except ImportError:
            raise HTTPException(status_code=500, detail="Installez openpyxl: python -m pip install openpyxl")
        try:
            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            sheet = workbook.active
            values = sheet.iter_rows(values_only=True)
            headers = [str(v).strip() if v is not None else "" for v in next(values)]
            if "parcelle_id" not in headers:
                raise HTTPException(status_code=400, detail="Colonne parcelle_id manquante")
            return [dict(zip(headers, row)) for row in values if any(v is not None for v in row)]
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Fichier Excel invalide: {exc}")
    raise HTTPException(status_code=400, detail="Format non supporté. Utilisez .csv ou .xlsx")


@router.post("/import")
async def import_soil_analyses(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = await _read_rows(file)
    if not rows:
        raise HTTPException(status_code=400, detail="Le fichier ne contient aucune ligne")
    farmer_id = _farmer_id(current_user)
    created = []
    try:
        for index, row in enumerate(rows, start=2):
            try:
                data = _parse_row(row)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=f"Ligne {index}: {exc}")
            if not get_owned_parcelle(db, data["parcelle_id"], farmer_id):
                raise HTTPException(status_code=404, detail=f"Ligne {index}: parcelle {data['parcelle_id']} introuvable")
            from app.models.sol import SoilAnalysis
            created.append(SoilAnalysis(**data))
        db.add_all(created)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"message": "Import terminé", "imported_count": len(created)}
