import os
from fastapi import HTTPException
from app.models.indicateur import IndicateurCalculation
from app.repositories.indicateur_repository import get_owned_parcelle

def _engine():
    try:
        from common import connectors as cn
        from indicateurs_service.indicateurs import get_indicateurs, saison
        from zonal_service.zonal import get_donnees_zonales
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Moteur d'indicateurs indisponible: {exc}")
    project = os.getenv("GEE_PROJECT")
    if not project:
        raise HTTPException(status_code=503, detail="GEE_PROJECT doit être défini pour activer Google Earth Engine.")
    try:
        cn.init_gee(project=project, service_account=os.getenv("GEE_SERVICE_ACCOUNT"), key_file=os.getenv("GEE_KEY_FILE"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Initialisation Google Earth Engine impossible: {exc}")
    return get_indicateurs, saison, get_donnees_zonales

def calculer(db, parcelle_id: int, farmer_id: int, culture: str, start: str | None, end: str | None, sol_mesure: dict | None = None):
    parcelle = get_owned_parcelle(db, parcelle_id, farmer_id)
    get_indicateurs, saison, get_donnees_zonales = _engine()
    if not (start and end):
        start, end = saison(culture)
    if start >= end:
        raise HTTPException(status_code=422, detail="La date de début doit précéder la date de fin (fin exclue).")
    p = {"lat": parcelle.latitude, "lon": parcelle.longitude, "surface_ha": parcelle.area_ha, "sol_mesure": sol_mesure or {}}
    donnees = {}
    if parcelle.geometry:
        try:
            donnees = get_donnees_zonales(parcelle.geometry, start, end)
        except Exception as exc:
            # Le moteur peut toujours exploiter les coordonnées du centroïde si disponibles.
            if parcelle.latitude is None or parcelle.longitude is None:
                raise HTTPException(status_code=422, detail=f"Calcul zonal impossible et coordonnées absentes: {exc}")
    if parcelle.latitude is None or parcelle.longitude is None:
        if not donnees.get("centroide"):
            raise HTTPException(status_code=422, detail="La parcelle doit avoir latitude/longitude ou une géométrie GeoJSON exploitable.")
    try:
        result = get_indicateurs(p, culture=culture, start=start, end=end, donnees=donnees)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    item = IndicateurCalculation(parcelle_id=parcelle_id, farmer_id=farmer_id, culture=culture,
        start_date=start, end_date=end, status="completed", result=result)
    db.add(item); db.commit(); db.refresh(item)
    return item

def serialize(item):
    return {"id": item.id, "parcelle_id": item.parcelle_id, "culture": item.culture,
        "periode": {"start": item.start_date, "end": item.end_date}, "status": item.status,
        "result": item.result, "error_message": item.error_message, "created_at": item.created_at}
