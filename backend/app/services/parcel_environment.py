"""Données environnementales réelles d'une parcelle (point = centroïde).

- NASA POWER (sans clé) : climat de la dernière année complète -> pluie, températures,
  ET0 (Hargreaves, FAO-56 éq. 52) par mois.
- ISRIC SoilGrids (sans clé) : pH, argile, sable, carbone organique (moyenne 0–30 cm).
- Google Earth Engine (GEE_PROJECT requis) : humidité du sol SMAP L4 (30 derniers jours),
  pluie GPM IMERG (12 derniers mois), NDVI MODIS (12 derniers mois).

Chaque source est indépendante : une source en échec est signalée dans `errors`
sans bloquer les autres. Le résultat est mis en cache dans la table
`parcel_environment` (migration 009) pendant CACHE_DAYS jours.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings

CACHE_DAYS = 7
MONTHS = ["janv", "févr", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc"]


def _ra_mm(lat: float, doy: int) -> float:
    """Rayonnement extraterrestre (mm/j équivalent), FAO-56 éq. 21."""
    phi = math.radians(lat)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    ra = 24 * 60 / math.pi * 0.0820 * dr * (ws * math.sin(phi) * math.sin(delta)
                                            + math.cos(phi) * math.cos(delta) * math.sin(ws))
    return 0.408 * ra


def climate_from_power(lat: float, lon: float, year: int) -> dict:
    from common import connectors as cn

    df = cn.fetch_power(lat, lon, f"{year}-01-01", f"{year}-12-31",
                        parameters=["T2M_MAX", "T2M_MIN", "T2M", "PRECTOTCORR"])
    df = df.dropna(subset=["T2M_MAX", "T2M_MIN", "T2M"])
    df["ET0"] = [0.0023 * (r.T2M + 17.8) * math.sqrt(max(r.T2M_MAX - r.T2M_MIN, 0)) * _ra_mm(lat, d.timetuple().tm_yday)
                 for d, r in df.iterrows()]
    monthly = []
    for m in range(1, 13):
        part = df[df.index.month == m]
        monthly.append({
            "month": m, "label": MONTHS[m - 1],
            "rain_mm": round(float(part.PRECTOTCORR.sum()), 1) if len(part) else None,
            "et0_mm": round(float(part.ET0.sum()), 1) if len(part) else None,
            "tmean_c": round(float(part.T2M.mean()), 1) if len(part) else None,
            "tmax_c": round(float(part.T2M_MAX.max()), 1) if len(part) else None,
            "tmin_c": round(float(part.T2M_MIN.min()), 1) if len(part) else None,
        })
    return {
        "source": "NASA POWER (community AG)", "year": year,
        "annual_rain_mm": round(float(df.PRECTOTCORR.sum()), 1),
        "annual_et0_mm": round(float(df.ET0.sum()), 1),
        "tmean_c": round(float(df.T2M.mean()), 1),
        "elevation_m": df.attrs.get("elevation"),
        "monthly": monthly,
    }


def soil_from_soilgrids(lat: float, lon: float) -> dict:
    from common import connectors as cn

    profile = cn.fetch_soilgrids(lat, lon)
    mean = cn.soil_profile_mean(profile, zr_cm=30)
    val = lambda k: None if k not in mean or math.isnan(mean[k]) else round(float(mean[k]), 2)  # noqa: E731
    if val("phh2o") is None and val("clay") is None:
        raise ValueError("SoilGrids n'a pas de données à ce point (zone urbaine, eau ou hors couverture).")
    return {"source": "ISRIC SoilGrids 250 m (estimation, 0–30 cm)", "ph": val("phh2o"), "clay_pct": val("clay"),
            "sand_pct": val("sand"), "silt_pct": val("silt"), "soc_g_kg": val("soc"), "nitrogen_g_kg": val("nitrogen")}


def gee_ready() -> tuple[bool, str | None]:
    if not settings.gee_project:
        return False, "GEE_PROJECT non défini dans backend/.env"
    if bool(settings.gee_service_account) != bool(settings.gee_key_file):
        return False, "GEE_SERVICE_ACCOUNT et GEE_KEY_FILE doivent être définis ensemble"
    return True, None


_gee_initialized = False


def _init_gee():
    global _gee_initialized
    from common import connectors as cn

    if not _gee_initialized:
        cn.init_gee(settings.gee_project, settings.gee_service_account or None, settings.gee_key_file or None)
        _gee_initialized = True
    return cn


def satellite_from_gee(lat: float, lon: float, today: date) -> tuple[dict, dict]:
    cn = _init_gee()
    out, errors = {}, {}
    start30 = (today - timedelta(days=30)).isoformat()
    start12 = (today.replace(day=1) - timedelta(days=365)).replace(day=1).isoformat()
    try:
        df = cn.fetch_smap(lat, lon, start30, today.isoformat()).dropna(how="all")
        out["soil_moisture"] = {
            "source": "NASA SMAP L4 (11 km, 30 derniers jours)",
            "surface_m3m3": round(float(df.sm_surface.mean()), 3),
            "rootzone_m3m3": round(float(df.sm_rootzone.mean()), 3),
            "rootzone_wetness": round(float(df.sm_rootzone_wetness.mean()), 3),
            "last_date": df.index.max().date().isoformat(),
        }
    except Exception as exc:  # noqa: BLE001
        errors["smap"] = f"{type(exc).__name__}: {exc}"[:300]
    try:
        s = cn.fetch_gpm_monthly(lat, lon, start12, today.replace(day=1).isoformat()).dropna()
        out["precipitation"] = {"source": "NASA GPM IMERG (mensuel)", "last_12_months_mm": round(float(s.sum()), 1),
                                "months": [{"month": d.strftime("%Y-%m"), "mm": round(float(v), 1)} for d, v in s.items()]}
    except Exception as exc:  # noqa: BLE001
        errors["gpm"] = f"{type(exc).__name__}: {exc}"[:300]
    try:
        df = cn.fetch_modis_vi(lat, lon, start12, today.isoformat()).dropna(how="all")
        out["vegetation"] = {"source": "NASA MODIS MOD13Q1 (250 m, 16 j)", "ndvi_mean": round(float(df.NDVI.mean()), 3),
                             "ndvi_max": round(float(df.NDVI.max()), 3), "images": int(len(df))}
    except Exception as exc:  # noqa: BLE001
        errors["modis"] = f"{type(exc).__name__}: {exc}"[:300]
    return out, errors


def collect(lat: float, lon: float, today: date | None = None) -> dict:
    today = today or date.today()
    data: dict[str, Any] = {"latitude": round(lat, 5), "longitude": round(lon, 5),
                            "fetched_at": datetime.utcnow().isoformat(timespec="seconds") + "Z", "errors": {}}
    try:
        data["climate"] = climate_from_power(lat, lon, today.year - 1)
    except Exception as exc:  # noqa: BLE001
        data["errors"]["nasa_power"] = f"{type(exc).__name__}: {exc}"[:300]
    try:
        data["soil"] = soil_from_soilgrids(lat, lon)
    except Exception as exc:  # noqa: BLE001
        data["errors"]["soilgrids"] = f"{type(exc).__name__}: {exc}"[:300]
    ready, reason = gee_ready()
    if ready:
        try:
            sat, errors = satellite_from_gee(lat, lon, today)
            data.update(sat)
            data["errors"].update(errors)
        except Exception as exc:  # noqa: BLE001
            data["errors"]["earth_engine"] = f"{type(exc).__name__}: {exc}"[:300]
    else:
        data["errors"]["earth_engine"] = reason
    return data


def get_for_parcel(db: Session, parcel, refresh: bool = False) -> dict | None:
    """Données en cache (< CACHE_DAYS jours) ou nouvelle collecte. None si la parcelle n'a pas de coordonnées."""
    if parcel.latitude is None or parcel.longitude is None:
        return None
    row = db.execute(text("SELECT data, fetched_at, latitude, longitude FROM parcel_environment WHERE parcelle_id=:id"),
                     {"id": parcel.id}).mappings().first()
    same_point = row is not None and abs(row["latitude"] - parcel.latitude) < 1e-4 and abs(row["longitude"] - parcel.longitude) < 1e-4
    if row and same_point and not refresh and row["fetched_at"] > datetime.utcnow() - timedelta(days=CACHE_DAYS):
        import json
        return json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
    data = collect(parcel.latitude, parcel.longitude)
    if not ("climate" in data or "soil" in data or "soil_moisture" in data):
        return data  # tout a échoué (réseau ?) : on ne met pas en cache
    import json
    db.execute(text("""
        INSERT INTO parcel_environment (parcelle_id, latitude, longitude, data, fetched_at)
        VALUES (:id, :lat, :lon, :data, :at)
        ON DUPLICATE KEY UPDATE latitude=VALUES(latitude), longitude=VALUES(longitude), data=VALUES(data), fetched_at=VALUES(fetched_at)
    """), {"id": parcel.id, "lat": parcel.latitude, "lon": parcel.longitude,
           "data": json.dumps(data, ensure_ascii=False), "at": datetime.utcnow()})
    db.commit()
    return data
