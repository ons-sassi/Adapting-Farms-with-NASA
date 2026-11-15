"""Routes consommées par l'interface React (frontend/src/api/client.js).

Elles traduisent le format JSON du frontend (camelCase, géométrie [[lat, lon], ...])
vers les tables et moteurs existants du backend (parcelles, soil_analyses, moteur
de rotation). Toutes les routes exigent un utilisateur connecté (JWT).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.models.app_analysis import AppAnalysis, AppSavedRotation
from app.models.parcelle import Parcelle
from app.models.sol import SoilAnalysis
from app.models.user import User
from app.services import frontend_catalog as catalog
from app.services import parcel_environment
from app.services.frontend_analysis_service import run_analysis

router = APIRouter(tags=["Interface web"])

FARM_ID = "main"
IRRIGATION_TO_DB = {"Pluviale": "none", "Goutte-à-goutte (limitée)": "drip", "Irrigation complète": "sprinkler"}
IRRIGATION_FROM_DB = {"none": "Pluviale", "drip": "Goutte-à-goutte (limitée)", "sprinkler": "Irrigation complète",
                      "surface": "Irrigation complète", "other": "Autre"}


# --------------------------------------------------------------------------- #
# Conversions
# --------------------------------------------------------------------------- #
class ParcelIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    crop: str | None = None
    zone: str | None = None
    irrigation: str | None = "Pluviale"
    areaHa: float | None = None
    geometry: list[list[float]] = Field(default_factory=list)
    ph: float | None = Field(default=None, ge=0, le=14)
    model_config = {"extra": "ignore"}


def _latest_ph(db: Session, parcelle_id: int) -> float | None:
    row = db.scalar(
        select(SoilAnalysis).where(SoilAnalysis.parcelle_id == parcelle_id, SoilAnalysis.ph.is_not(None))
        .order_by(SoilAnalysis.sampled_at.desc(), SoilAnalysis.id.desc())
    )
    return row.ph if row else None


def _status(ph: float | None) -> str:
    if ph is None or 6.0 <= ph <= 8.0:
        return "ok"
    return "warning" if 5.5 <= ph <= 8.5 else "alert"


def _geometry_to_front(geometry: dict | None) -> list[list[float]]:
    if not geometry:
        return []
    geom = geometry.get("geometry", geometry)
    if geom.get("type") != "Polygon" or not geom.get("coordinates"):
        return []
    ring = geom["coordinates"][0]
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    return [[lat, lon] for lon, lat, *_ in ring]


def _geometry_to_db(points: list[list[float]]) -> dict | None:
    if len(points) < 3:
        return None
    ring = [[lon, lat] for lat, lon in points]
    return {"type": "Polygon", "coordinates": [ring + [ring[0]]]}


def parcel_to_front(p: Parcelle, ph: float | None) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "farmId": FARM_ID,
        "name": p.name,
        "crop": p.current_crop or "",
        "areaHa": p.area_ha,
        "updatedAt": p.updated_at.date().isoformat() if p.updated_at else None,
        "irrigation": IRRIGATION_FROM_DB.get(p.irrigation_type, p.irrigation_type),
        "irrigationType": p.irrigation_type,
        "zone": p.zone or "",
        "ph": ph,
        "status": _status(ph),
        "geometry": _geometry_to_front(p.geometry),
        "latitude": p.latitude,
        "longitude": p.longitude,
    }


def _owned_parcel(db: Session, parcel_id: str, user: User) -> Parcelle:
    if not str(parcel_id).isdigit():
        raise HTTPException(404, "Parcelle introuvable.")
    parcel = db.scalar(select(Parcelle).where(Parcelle.id == int(parcel_id), Parcelle.farmer_id == user.id))
    if parcel is None:
        raise HTTPException(404, "Parcelle introuvable.")
    return parcel


def _apply_parcel(parcel: Parcelle, data: ParcelIn) -> None:
    parcel.name = data.name
    parcel.current_crop = data.crop or None
    parcel.zone = data.zone or None
    parcel.irrigation_type = IRRIGATION_TO_DB.get(data.irrigation or "", "none")
    geometry = _geometry_to_db(data.geometry)
    if geometry is not None:
        parcel.geometry = geometry
        parcel.latitude = sum(p[0] for p in data.geometry) / len(data.geometry)
        parcel.longitude = sum(p[1] for p in data.geometry) / len(data.geometry)
    if data.areaHa and data.areaHa > 0:
        parcel.area_ha = round(data.areaHa, 4)


def _save_ph(db: Session, parcel: Parcelle, ph: float | None) -> None:
    if ph is not None and ph != _latest_ph(db, parcel.id):
        db.add(SoilAnalysis(parcelle_id=parcel.id, ph=ph, source="manual", notes="Saisi depuis l'interface web"))


# --------------------------------------------------------------------------- #
# Exploitations et parcelles
# --------------------------------------------------------------------------- #
@router.get("/farms")
def list_farms(user: User = Depends(get_current_user)):
    return [{"id": FARM_ID, "name": f"Exploitation de {user.full_name}"}]


@router.get("/parcels")
def list_parcels(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    parcels = db.scalars(select(Parcelle).where(Parcelle.farmer_id == user.id).order_by(Parcelle.updated_at.desc())).all()
    return [parcel_to_front(p, _latest_ph(db, p.id)) for p in parcels]


@router.get("/parcels/{parcel_id}")
def get_parcel(parcel_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    parcel = _owned_parcel(db, parcel_id, user)
    return parcel_to_front(parcel, _latest_ph(db, parcel.id))


@router.post("/parcels", status_code=status.HTTP_201_CREATED)
def create_parcel(data: ParcelIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if len(data.geometry) < 3:
        raise HTTPException(422, "Délimitez la parcelle (au moins 3 points).")
    if not data.areaHa or data.areaHa <= 0:
        raise HTTPException(422, "Surface de la parcelle invalide.")
    parcel = Parcelle(farmer_id=user.id, name=data.name, area_ha=data.areaHa)
    _apply_parcel(parcel, data)
    db.add(parcel)
    db.flush()
    _save_ph(db, parcel, data.ph)
    db.commit()
    db.refresh(parcel)
    return parcel_to_front(parcel, _latest_ph(db, parcel.id))


@router.patch("/parcels/{parcel_id}")
def update_parcel(parcel_id: str, data: ParcelIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    parcel = _owned_parcel(db, parcel_id, user)
    _apply_parcel(parcel, data)
    _save_ph(db, parcel, data.ph)
    db.commit()
    db.refresh(parcel)
    return parcel_to_front(parcel, _latest_ph(db, parcel.id))


@router.delete("/parcels/{parcel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_parcel(parcel_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(_owned_parcel(db, parcel_id, user))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/parcels/{parcel_id}/environment")
def parcel_env(parcel_id: str, refresh: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Climat (NASA POWER), sol (SoilGrids) et, si Earth Engine est configuré, SMAP / GPM / MODIS."""
    parcel = _owned_parcel(db, parcel_id, user)
    data = parcel_environment.get_for_parcel(db, parcel, refresh=refresh)
    if data is None:
        raise HTTPException(422, "La parcelle n'a pas de coordonnées : délimitez-la sur la carte.")
    return data


# --------------------------------------------------------------------------- #
# État de la configuration (page Paramètres)
# --------------------------------------------------------------------------- #
@router.get("/status")
def service_status(check: bool = False, db: Session = Depends(get_db)):
    """Ce qui est configuré côté serveur. Ne renvoie jamais de secret, seulement des états.
    check=true : teste aussi en direct NASA POWER, SoilGrids et Earth Engine (quelques secondes)."""
    from bd.config import DB_NAME, TABLE_CULTURE

    try:
        db.execute(select(1))
        mysql = {"ok": True, "detail": settings.mysql_database}
    except Exception as exc:  # noqa: BLE001
        mysql = {"ok": False, "detail": type(exc).__name__}
    try:
        from bd.cultures import lister_cultures
        n = len(lister_cultures())
        catalogue = {"ok": n > 0, "detail": f"{n} culture(s) dans {DB_NAME}.{TABLE_CULTURE}"}
    except Exception as exc:  # noqa: BLE001
        catalogue = {"ok": False, "detail": f"{DB_NAME}.{TABLE_CULTURE} indisponible ({type(exc).__name__}) : "
                                            "voir database/catalogue/001_create_culture.sql"}
    gee_ok, gee_reason = parcel_environment.gee_ready()
    try:
        import google.genai  # noqa: F401
        genai_installed = True
    except ImportError:
        genai_installed = False
    result = {
        "mysql": mysql,
        "catalogue_indicateurs": catalogue,
        "catalogue_interface": {"ok": True, "detail": f"{len(catalog.list_crops())} cultures (fichiers CSV)"},
        "nasa_power": {"ok": True, "detail": "Sans clé (accès Internet requis)"},
        "soilgrids": {"ok": True, "detail": "Sans clé (accès Internet requis)"},
        "earth_engine": {"ok": gee_ok, "detail": f"Projet {settings.gee_project}" if gee_ok else gee_reason},
        "groq": {"ok": bool(settings.groq_api_key), "detail": settings.groq_model if settings.groq_api_key else "GROQ_API_KEY non défini"},
        "gemini": {"ok": bool(settings.gemini_api_key) and genai_installed,
                   "detail": settings.extractor_model if settings.gemini_api_key and genai_installed
                   else ("pip install google-genai" if settings.gemini_api_key else "GEMINI_API_KEY non défini")},
        "jwt": {"ok": settings.jwt_secret_key != "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET" and len(settings.jwt_secret_key) >= 32,
                "detail": "Clé personnalisée" if settings.jwt_secret_key != "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET" else "Clé par défaut : à changer"},
    }
    if check:
        result.update(_live_checks(gee_ok))
    result["checked_live"] = check
    return result


def _timed(fn) -> dict:
    """Exécute un test réseau et renvoie {ok, detail} avec la durée."""
    import time
    t0 = time.time()
    try:
        detail = fn()
        return {"ok": True, "detail": f"Répond ({time.time() - t0:.1f} s){' · ' + detail if detail else ''}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"Ne répond pas : {type(exc).__name__} {str(exc)[:120]}"}


def _live_checks(gee_ok: bool) -> dict:
    import httpx

    def power():
        r = httpx.get("https://power.larc.nasa.gov/api/temporal/daily/point", timeout=15, params={
            "parameters": "T2M", "community": "AG", "latitude": 35.68, "longitude": 10.1,
            "start": "20240101", "end": "20240101", "format": "JSON"})
        r.raise_for_status()
        return ""

    def soilgrids():
        r = httpx.get("https://rest.isric.org/soilgrids/v2.0/properties/query", timeout=20, params={
            "lat": 35.68, "lon": 10.1, "property": "phh2o", "depth": "0-5cm", "value": "mean"})
        r.raise_for_status()
        return ""

    def earth_engine():
        cn = parcel_environment._init_gee()
        return f"projet {settings.gee_project}" if cn._require_ee().Number(1).add(1).getInfo() == 2 else ""

    out = {"nasa_power": _timed(power), "soilgrids": _timed(soilgrids)}
    if gee_ok:
        out["earth_engine"] = _timed(earth_engine)
    return out


# --------------------------------------------------------------------------- #
# Catalogue des cultures
# --------------------------------------------------------------------------- #
@router.get("/crops")
def list_crops(eligible_only: bool = False):
    return catalog.list_crops(eligible_only)


# --------------------------------------------------------------------------- #
# Analyses de rotation
# --------------------------------------------------------------------------- #
class AnalysisIn(BaseModel):
    parcelId: str
    crops: list[str] = Field(min_length=2)
    priorities: dict[str, float] = Field(default_factory=dict)
    horizon: int = 4
    constraints: dict[str, Any] = Field(default_factory=dict)


def analysis_to_front(a: AppAnalysis) -> dict[str, Any]:
    return {
        **a.request,
        **a.result,
        "id": str(a.id),
        "parcelId": str(a.parcelle_id),
        "createdAt": a.created_at.date().isoformat() if a.created_at else None,
    }


def _owned_analysis(db: Session, analysis_id: str, user: User) -> AppAnalysis:
    if not str(analysis_id).isdigit():
        raise HTTPException(404, "Analyse introuvable.")
    a = db.scalar(select(AppAnalysis).where(AppAnalysis.id == int(analysis_id), AppAnalysis.farmer_id == user.id))
    if a is None:
        raise HTTPException(404, "Analyse introuvable.")
    return a


@router.get("/analyses")
def list_analyses(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(AppAnalysis).where(AppAnalysis.farmer_id == user.id).order_by(AppAnalysis.id.desc())).all()
    return [analysis_to_front(a) for a in rows]


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return analysis_to_front(_owned_analysis(db, analysis_id, user))


@router.post("/analyses", status_code=status.HTTP_201_CREATED)
def create_analysis(data: AnalysisIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    parcel = _owned_parcel(db, data.parcelId, user)
    front_parcel = parcel_to_front(parcel, _latest_ph(db, parcel.id))
    request = data.model_dump(exclude={"parcelId"})
    try:  # données réelles (NASA POWER, SoilGrids...) ; l'analyse reste possible sans elles
        environment = parcel_environment.get_for_parcel(db, parcel)
    except Exception as exc:  # noqa: BLE001
        environment = {"errors": {"environment": f"{type(exc).__name__}: {exc}"[:300]}}
    result = run_analysis(request, front_parcel, front_parcel["ph"], environment=environment)
    if not result["rotations"]:
        raise HTTPException(422, result.get("notice") or "Aucune rotation possible avec ces cultures.")
    request["horizon"] = result["horizon"]
    analysis = AppAnalysis(farmer_id=user.id, parcelle_id=parcel.id, request=request, result=result)
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis_to_front(analysis)


@router.post("/analyses/{analysis_id}/saved-rotations", status_code=status.HTTP_201_CREATED)
def save_rotation(analysis_id: str, rotation: dict[str, Any], db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    analysis = _owned_analysis(db, analysis_id, user)
    key = str(rotation.get("id") or "")
    if key not in {r["id"] for r in analysis.result.get("rotations", [])}:
        raise HTTPException(404, "Rotation inconnue pour cette analyse.")
    stored = next(r for r in analysis.result["rotations"] if r["id"] == key)
    row = db.scalar(select(AppSavedRotation).where(AppSavedRotation.analysis_id == analysis.id,
                                                   AppSavedRotation.rotation_key == key))
    if row is None:
        row = AppSavedRotation(farmer_id=user.id, analysis_id=analysis.id, rotation_key=key, rotation=stored)
        db.add(row)
        db.commit()
        db.refresh(row)
    return {**row.rotation, "analysisId": str(analysis.id), "savedAt": row.saved_at.date().isoformat()}


@router.get("/saved-rotations")
def list_saved_rotations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(AppSavedRotation).where(AppSavedRotation.farmer_id == user.id)
                      .order_by(AppSavedRotation.id.desc())).all()
    return [{**r.rotation, "analysisId": str(r.analysis_id), "savedAt": r.saved_at.date().isoformat()} for r in rows]


# --------------------------------------------------------------------------- #
# Chatbot (Groq) et extraction de documents (Gemini)
# --------------------------------------------------------------------------- #
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=20)


CHAT_PROMPT = (
    "Tu es l'assistant agronomique d'AgriSense, une application tunisienne d'aide au choix des "
    "rotations de cultures. Réponds en français, simplement et brièvement, à un agriculteur. "
    "Appuie-toi sur le contexte fourni (parcelles, dernière analyse). Si une donnée manque, dis-le "
    "au lieu d'inventer, et conseille de vérifier auprès d'un conseiller agricole pour les décisions importantes."
)


@router.post("/chat")
async def chat(data: ChatIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.services.llm.groq_client import GroqNotConfiguredError, create_groq_client

    parcels = list_parcels(db, user)
    last = db.scalar(select(AppAnalysis).where(AppAnalysis.farmer_id == user.id).order_by(AppAnalysis.id.desc()))
    context = {
        "parcelles": [{k: p[k] for k in ("name", "crop", "areaHa", "irrigation", "zone", "ph")} for p in parcels],
        "derniere_analyse": None if last is None else {
            "rotations": [{"nom": r["name"], "score": r["score"], "cultures": r["years"]} for r in last.result["rotations"]],
        },
    }
    try:
        client = create_groq_client()
    except GroqNotConfiguredError:
        raise HTTPException(503, "Assistant non configuré : ajoutez GROQ_API_KEY dans backend/.env.")
    history = [{"role": m.get("role", "user"), "content": m.get("content", "")} for m in data.history
               if m.get("role") in ("user", "assistant")]
    try:
        completion = await client.chat.completions.create(
            model=settings.groq_model,
            messages=[{"role": "system", "content": CHAT_PROMPT + f"\nContexte : {context}"},
                      *history, {"role": "user", "content": data.message}],
            max_completion_tokens=800,
            temperature=0.3,
        )
    except Exception as exc:  # réseau, quota, clé refusée
        raise HTTPException(502, f"Assistant indisponible ({exc.__class__.__name__}).") from exc
    return {"answer": completion.choices[0].message.content or ""}


MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@router.post("/documents/extract")
def extract_document(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    """PDF ou image -> JSON des données trouvées (Gemini), + pH du sol s'il est détecté."""
    from app.services.document_extractor import (
        ExternalSourceError, UnsupportedDocumentError, extract_document as extract, find_soil_ph,
    )
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Fichier trop volumineux (20 Mo maximum).")
    try:
        data = extract(content)
    except UnsupportedDocumentError as exc:
        raise HTTPException(415, str(exc))
    except ExternalSourceError as exc:
        raise HTTPException(502, str(exc))
    return {"data": data, "ph": find_soil_ph(data)}