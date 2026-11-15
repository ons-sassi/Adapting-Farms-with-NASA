"""
connectors.py : accès aux 6 sources du PDF.

  NASA POWER  -> API REST directe (aucun compte)
  SoilGrids   -> API REST ISRIC (aucun compte, ~5 requêtes/min max)
  SMAP, GPM, MODIS, SRTM -> Google Earth Engine (compte GEE + projet Cloud requis)

Nouveautés par rapport à la v1 :
  * SMAP L4 version 008 (la 007 est remplacée et s'arrête en juin 2025)
  * masques qualité MODIS (nuages / neige / mauvaise qualité)
  * cache disque (décorateur @cached) : indispensable pour une application web
  * tolérance aux collections vides (colonnes toujours présentes, valeurs NaN)
  * last_available() : dernière date réellement disponible d'une collection GEE
  * init_gee() compatible compte de service (serveur)

Première utilisation de GEE en local :  `earthengine authenticate`.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import pickle
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import requests

# --------------------------------------------------------------------------- #
# Cache disque
# --------------------------------------------------------------------------- #
CACHE_DIR = Path(os.environ.get("ROTATION_CACHE_DIR", ".cache_indicateurs"))
CACHE_TTL_S = 7 * 24 * 3600
CACHE_VERSION = "6"


def cached(ttl: int = CACHE_TTL_S):
    """Met en cache le résultat d'une fonction (clé = nom + arguments)."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

            # La version majeure de pandas fait partie de la clé : un pickle de DataFrame
            # n'est pas portable d'une version majeure à l'autre.
            raw = json.dumps([CACHE_VERSION, pd.__version__.split(".")[0], fn.__module__,
                              fn.__qualname__, args, kwargs], sort_keys=True, default=str)

            path = CACHE_DIR / f"{fn.__name__}_{hashlib.md5(raw.encode()).hexdigest()}.pkl"
            if path.exists() and time.time() - path.stat().st_mtime < ttl:
                try:
                    return pickle.loads(path.read_bytes())
                except (pickle.UnpicklingError, EOFError, AttributeError,
                        ImportError, AssertionError, ValueError, TypeError) as exc:
                    # cache corrompu ou écrit par une autre version de pandas : on recalcule
                    warnings.warn(f"Cache illisible ({path.name}) : {type(exc).__name__}. "
                                  "Recalcul.", RuntimeWarning, stacklevel=2)
            out = fn(*args, **kwargs)
            if out is not None:
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(pickle.dumps(out))
                tmp.replace(path)
            return out
        return wrapper
    return deco


# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #
def _get(url, params=None, retries=4, timeout=120):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if i == retries - 1:
                raise
            time.sleep(4 * (i + 1))


_ee = None



def init_gee(
    project: str,
    service_account: str | None = None,
    key_file: str | None = None
):
    """
    Initialise Google Earth Engine.

    Mode local :
        init_gee(project="mon-projet")
        Authentification préalable avec : earthengine authenticate

    Mode serveur :
        init_gee(
            project="mon-projet",
            service_account="compte@projet.iam.gserviceaccount.com",
            key_file="chemin/vers/credentials.json"
        )
    """
    global _ee

    import ee

    if not project:
        raise ValueError("Le project Google Cloud est obligatoire.")

    # Les deux paramètres doivent être fournis ensemble.
    if bool(service_account) != bool(key_file):
        raise ValueError(
            "service_account et key_file doivent être fournis ensemble."
        )

    try:
        if service_account and key_file:
            # Authentification serveur avec compte de service.
            credentials = ee.ServiceAccountCredentials(
                service_account,
                key_file
            )
            ee.Initialize(credentials, project=project)

        else:
            # Authentification locale déjà configurée.
            ee.Initialize(project=project)

    except Exception as exc:
        if service_account:
            message = (
                "Impossible d'initialiser Google Earth Engine avec "
                "le compte de service. Vérifie l'adresse du compte, "
                "le fichier JSON, les permissions et le projet Google Cloud."
            )
        else:
            message = (
                "Impossible d'initialiser Google Earth Engine. "
                "Vérifie ton projet Google Cloud et ton authentification. "
                "En local, exécute d'abord : earthengine authenticate"
            )

        raise RuntimeError(message) from exc

    _ee = ee
    return ee



def _require_ee():
    if _ee is None:
        raise RuntimeError("Earth Engine non initialisé : appelle d'abord init_gee(project=...).")
    return _ee


def _point(lat, lon):
    return _require_ee().Geometry.Point([lon, lat])


# --------------------------------------------------------------------------- #
# Géométrie de la parcelle (GeoJSON, lon/lat) : sans dépendance externe
# --------------------------------------------------------------------------- #

def normalize_polygon(geometry: dict) -> dict:
    """
    Accepte Polygon, MultiPolygon, Feature ou FeatureCollection.
    Conserve toutes les parties d'un MultiPolygon.
    Retourne une géométrie GeoJSON Polygon ou MultiPolygon.
    """
    if not isinstance(geometry, dict):
        raise ValueError("La géométrie doit être un dictionnaire GeoJSON.")

    g = geometry

    if g.get("type") == "FeatureCollection":
        features = g.get("features", [])
        if not features:
            raise ValueError("FeatureCollection vide.")
        g = features[0]

    if g.get("type") == "Feature":
        g = g.get("geometry")

    if not isinstance(g, dict):
        raise ValueError("Géométrie GeoJSON invalide ou absente.")

    geom_type = g.get("type")
    coordinates = g.get("coordinates")

    if geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError(
            f"Géométrie non supportée : {geom_type} "
            "(Polygon ou MultiPolygon attendu)"
        )

    if not isinstance(coordinates, list) or not coordinates:
        raise ValueError("Les coordonnées de la géométrie sont vides.")

    polygons = [coordinates] if geom_type == "Polygon" else coordinates

    for polygon in polygons:
        if not isinstance(polygon, list) or not polygon:
            raise ValueError("Un polygone ne contient aucun anneau.")

        for ring in polygon:
            if not isinstance(ring, list) or len(ring) < 4:
                raise ValueError("Un anneau doit contenir au moins 4 points.")

            points = np.asarray(ring, dtype=float)

            if points.ndim != 2 or points.shape[1] < 2:
                raise ValueError("Coordonnées GeoJSON invalides.")

            if not np.isfinite(points[:, :2]).all():
                raise ValueError("Les coordonnées contiennent des valeurs invalides.")

            if not np.allclose(points[0, :2], points[-1, :2]):
                raise ValueError("Un anneau GeoJSON doit être fermé.")

    return {
        "type": geom_type,
        "coordinates": coordinates
    }


def _polygon_parts(geometry):
    """Retourne les anneaux de chaque polygone."""
    g = normalize_polygon(geometry)

    if g["type"] == "Polygon":
        return [g["coordinates"]]

    return g["coordinates"]


def _ring_metrics(ring):
    """Retourne l'aire planaire absolue et le centroïde d'un anneau."""
    points = np.asarray(ring, dtype=float)[:, :2]
    x, y = points[:, 0], points[:, 1]

    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cross = x * y1 - x1 * y

    signed_area = cross.sum() / 2
    area = abs(signed_area)

    if area < 1e-14:
        return 0.0, (float(x.mean()), float(y.mean()))

    cx = ((x + x1) * cross).sum() / (6 * signed_area)
    cy = ((y + y1) * cross).sum() / (6 * signed_area)

    return area, (float(cx), float(cy))


def poly_centroid(geometry: dict) -> tuple[float, float]:
    """Retourne le centroïde (lat, lon) de la géométrie complète."""
    weighted_x = 0.0
    weighted_y = 0.0
    total_area = 0.0
    fallback = []

    for polygon in _polygon_parts(geometry):
        for index, ring in enumerate(polygon):
            area, (cx, cy) = _ring_metrics(ring)

            if index == 0:
                sign = 1
                fallback.extend(np.asarray(ring)[:-1, :2].tolist())
            else:
                sign = -1

            weighted_x += sign * area * cx
            weighted_y += sign * area * cy
            total_area += sign * area

    if total_area <= 1e-14:
        if not fallback:
            raise ValueError("Impossible de calculer le centroïde.")
        points = np.asarray(fallback)
        return float(points[:, 1].mean()), float(points[:, 0].mean())

    return (
        float(weighted_y / total_area),
        float(weighted_x / total_area)
    )


def poly_area_m2(geometry: dict) -> float:
    """Calcule l'aire approximative totale en m², en tenant compte des trous."""
    polygons = _polygon_parts(geometry)

    exterior_points = [
        np.asarray(polygon[0], dtype=float)[:, :2]
        for polygon in polygons
    ]

    all_points = np.vstack(exterior_points)
    lat0 = np.radians(all_points[:, 1].mean())

    total_area = 0.0

    for polygon in polygons:
        for index, ring in enumerate(polygon):
            points = np.asarray(ring, dtype=float)[:, :2]

            x = points[:, 0] * 111_320.0 * np.cos(lat0)
            y = points[:, 1] * 111_320.0

            area = abs(
                (x * np.roll(y, -1) - np.roll(x, -1) * y).sum() / 2
            )

            total_area += area if index == 0 else -area

    return float(max(0.0, total_area))


def points_in_polygon(
    geometry: dict,
    n: int = 4,
    grid: int = 7
) -> list[tuple[float, float]]:
    """
    Retourne jusqu'à n points (lat, lon) répartis dans tous les polygones.
    Les trous sont exclus.
    """
    if n <= 0:
        return []

    polygons = _polygon_parts(geometry)

    def inside_ring(px, py, ring):
        points = np.asarray(ring, dtype=float)[:, :2]
        x, y = points[:, 0], points[:, 1]

        inside = False

        for i in range(len(points) - 1):
            if (y[i] > py) != (y[i + 1] > py):
                intersection = (
                    (x[i + 1] - x[i]) * (py - y[i])
                    / (y[i + 1] - y[i]) + x[i]
                )
                if px < intersection:
                    inside = not inside

        return inside

    def inside_polygon(px, py, polygon):
        if not inside_ring(px, py, polygon[0]):
            return False

        return not any(
            inside_ring(px, py, hole)
            for hole in polygon[1:]
        )

    def inside_geometry(px, py):
        return any(
            inside_polygon(px, py, polygon)
            for polygon in polygons
        )

    exterior_points = [
        np.asarray(polygon[0], dtype=float)[:, :2]
        for polygon in polygons
    ]

    all_points = np.vstack(exterior_points)

    gx = np.linspace(all_points[:, 0].min(), all_points[:, 0].max(), grid + 2)[1:-1]
    gy = np.linspace(all_points[:, 1].min(), all_points[:, 1].max(), grid + 2)[1:-1]

    candidates = []

    clat, clon = poly_centroid(geometry)

    if inside_geometry(clon, clat):
        candidates.append((clat, clon))

    for py in gy:
        for px in gx:
            if inside_geometry(px, py):
                point = (float(py), float(px))

                if point not in candidates:
                    candidates.append(point)

    if candidates:
        step = max(1, len(candidates) // max(1, n))
        selected = candidates[::step][:n]

        return selected

    # Cas exceptionnel : géométrie trop petite pour la grille.
    first = exterior_points[0]
    return [(float(first[:, 1].mean()), float(first[:, 0].mean()))]


def _region(lat, lon, geometry, scale):
    """Polygone si la parcelle couvre au moins un pixel (scale x scale), sinon le point
    (un polygone plus petit qu'un pixel peut renvoyer une valeur vide)."""
    ee = _require_ee()
    if geometry is not None and poly_area_m2(geometry) >= scale ** 2:
        return ee.Geometry(normalize_polygon(geometry), None, False)
    return _point(lat, lon)


def _empty(cols=None) -> pd.DataFrame:
    return pd.DataFrame(columns=list(cols or []), index=pd.DatetimeIndex([], name="date"), dtype=float)


def _rows_to_df(rows, cols=None) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty or "date" not in df:
        return _empty(cols)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df = df.reindex(columns=cols) if cols else df
    # Une colonne entièrement vide (None) serait de type object : on force float (NaN).
    return df.apply(pd.to_numeric, errors="raise").astype(float)



def _gee_daily(ic, pt, scale, start, end, agg="mean", chunk=45, cols=None):
    """
    Extraction journalière depuis Google Earth Engine.

    Convention :
        start inclus
        end exclu

    Pour agg='sum', une journée GPM IMERG est valide
    uniquement si elle contient 48 images.

    Les journées incomplètes sont conservées avec NaN.

    Les requêtes sont exécutées par lots de `chunk` jours.
    """
    ee = _require_ee()

    if agg not in ("sum", "mean"):
        raise ValueError("agg doit être 'sum' ou 'mean'.")

    if chunk <= 0:
        raise ValueError("chunk doit être strictement positif.")

    cols = cols or []

    days = pd.date_range(
        start=start,
        end=end,
        freq="D",
        inclusive="left"
    )

    if len(days) == 0:
        return _empty(cols)

    all_rows = []

    for offset in range(0, len(days), chunk):
        batch = days[offset:offset + chunk]

        features = []

        for d in batch:
            start_day = ee.Date(d.strftime("%Y-%m-%d"))
            end_day = start_day.advance(1, "day")

            sub = ic.filterDate(start_day, end_day)
            count = sub.size()

            if agg == "sum":
                valid = count.eq(IMERG_HALFHOURS_PER_DAY)
                img = sub.sum()
            else:
                valid = count.gt(0)
                img = sub.mean()

            values = ee.Dictionary(
                ee.Algorithms.If(
                    valid,
                    img.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=pt,
                        scale=scale,
                        maxPixels=1e9
                    ),
                    ee.Dictionary({})
                )
            )

            feature = ee.Feature(
                None,
                values.set(
                    "date",
                    start_day.format("YYYY-MM-dd")
                )
            )

            features.append(feature)

        fc = ee.FeatureCollection(features)

        result = fc.getInfo()

        for feature in result.get("features", []):
            properties = feature.get("properties", {})

            row = {"date": properties.get("date")}

            for col in cols:
                row[col] = properties.get(col, np.nan)

            all_rows.append(row)

    return _rows_to_df(all_rows, cols)


def _gee_images(ic, geom, scale, start, end, reducer=None, cols=None):
    """Une ligne par image (composites MODIS, mensuels IMERG...)."""
    ee = _require_ee()
    reducer = reducer or ee.Reducer.mean()
    ic = ic.filterDate(start, end)

    def f(img):
        d = img.reduceRegion(reducer, geom, scale)
        return ee.Feature(None, d.set("date", img.date().format("YYYY-MM-dd")))

    rows = [x["properties"] for x in ee.FeatureCollection(ic.map(f)).getInfo()["features"]]
    return _rows_to_df(rows, cols)


@cached(ttl=24 * 3600)
def last_available(collection_id: str) -> str:
    """Date ('YYYY-MM-DD') de la dernière image disponible d'une collection GEE."""
    ee = _require_ee()
    ic = ee.ImageCollection(collection_id)
    return ic.sort("system:time_start", False).first().date().format("YYYY-MM-dd").getInfo()


# --------------------------------------------------------------------------- #
# 1. NASA POWER
# --------------------------------------------------------------------------- #
POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_PARAMS = ["T2M_MAX", "T2M_MIN", "T2M", "PRECTOTCORR", "ALLSKY_SFC_SW_DWN",
                "RH2M", "WS2M", "T2MDEW"]


@cached()
def fetch_power(lat, lon, start, end, parameters=None) -> pd.DataFrame:
    """start/end 'YYYY-MM-DD'. DataFrame journalier ; df.attrs['elevation'] = altitude (m)."""
    parameters = parameters or POWER_PARAMS
    js = _get(POWER_URL, {
        "parameters": ",".join(parameters), "community": "AG",
        "longitude": lon, "latitude": lat,
        "start": start.replace("-", ""), "end": end.replace("-", ""), "format": "JSON",
    })
    if "properties" not in js:
        raise RuntimeError(f"Réponse POWER inattendue : {js.get('messages') or js}")
    df = pd.DataFrame(js["properties"]["parameter"])
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "date"
    df = df.replace(-999, np.nan)          # -999 = valeur manquante POWER
    df.attrs["elevation"] = js["geometry"]["coordinates"][2]
    return df


# --------------------------------------------------------------------------- #
# 2. GPM / IMERG  (via GEE)
# --------------------------------------------------------------------------- #
IMERG_HH = "NASA/GPM_L3/IMERG_V07"              # 30 min, 'precipitation' (mm/h) ; status provisional -> permanent
IMERG_MONTHLY = "NASA/GPM_L3/IMERG_MONTHLY_V07"  # mensuel, mm/h
# Les images IMERG `provisional` sont remplacées plus tard par des images `permanent` :
# cache court (24 h) pour ne pas figer une valeur provisoire pendant 7 jours.
GPM_CACHE_TTL_S = 24 * 3600
IMERG_HALFHOURS_PER_DAY = 48


def classify_status(statuses) -> str:
    """Statut de publication agrégé d'un lot d'images IMERG (propriété GEE `status`).

    no_data     : aucune image
    permanent   : toutes les images sont `permanent` (version finale)
    provisional : toutes les images sont `provisional`
    mixed       : mélange permanent + provisional
    unknown     : au moins une valeur inattendue (ou propriété absente)
    """
    values = set(statuses or [])
    if not values:
        return "no_data"
    if values == {"permanent"}:
        return "permanent"
    if values == {"provisional"}:
        return "provisional"
    if values == {"permanent", "provisional"}:
        return "mixed"
    return "unknown"


@cached(ttl=GPM_CACHE_TTL_S)
def fetch_gpm_daily(lat, lon, start, end) -> pd.DataFrame:
    """Pluie journalière (mm) = somme des demi-heures (mm/h x 0.5). Colonne 'precip_mm'.

    Convention : start inclus, end exclu. Une ligne par jour du calendrier ; un jour qui n'a
    pas exactement 48 images vaut NaN (jamais 0). Jour = jour UTC.
    Les images récentes sont `provisional` (voir fetch_gpm_daily_status) ; la dernière date
    disponible s'obtient avec last_available(IMERG_HH) (dernier jour souvent incomplet)."""
    ee = _require_ee()
    ic = (ee.ImageCollection(IMERG_HH).select("precipitation")
          .map(lambda im: im.multiply(0.5).copyProperties(im, ["system:time_start"])))
    df = _gee_daily(ic, _point(lat, lon), 11132, start, end, agg="sum", chunk=45,
                    cols=["precipitation"])
    return df.rename(columns={"precipitation": "precip_mm"})


@cached(ttl=GPM_CACHE_TTL_S)
def fetch_gpm_daily_status(start, end) -> pd.DataFrame:
    """
    Récupère le statut des images GPM IMERG V07 par jour.

    Valeurs possibles : permanent, provisional, mixed, unknown, no_data
    (voir classify_status).

    Convention : start inclus, end exclu.
    """
    ee = _require_ee()

    ic = ee.ImageCollection(IMERG_HH)
    days = pd.date_range(
        start=start,
        end=end,
        freq="D",
        inclusive="left"
    )

    rows = []

    for offset in range(0, len(days), 45):
        batch = days[offset:offset + 45]
        features = []

        for day in batch:
            date = day.strftime("%Y-%m-%d")
            start_day = ee.Date(date)
            end_day = start_day.advance(1, "day")

            sub = ic.filterDate(start_day, end_day)
            statuses = sub.aggregate_array("status")

            feature = ee.Feature(None, {
                "date": date,
                "statuses": statuses
            })
            features.append(feature)

        result = ee.FeatureCollection(features).getInfo()

        for feature in result.get("features", []):
            props = feature.get("properties", {})
            status = classify_status(props.get("statuses"))

            rows.append({
                "date": props.get("date"),
                "status": status
            })

    if not rows:
        return pd.DataFrame(columns=["status"])

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def fetch_gpm_monthly(
    lat,
    lon,
    start="2000-06-01",
    end=None
) -> pd.Series:
    """
    Cumuls mensuels GPM IMERG en mm (mm/h moyen x 24 x nombre de jours du mois).
    Les mois sans données sont conservés avec NaN.

    Convention :
    - start inclus
    - end exclu (défaut : aujourd'hui, résolu ICI pour faire partie de la clé de cache)
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    return _fetch_gpm_monthly(lat, lon, start, end)


@cached(ttl=GPM_CACHE_TTL_S)
def _fetch_gpm_monthly(lat, lon, start, end) -> pd.Series:
    ee = _require_ee()

    ic = ee.ImageCollection(IMERG_MONTHLY).select("precipitation")

    df = _gee_images(
        ic,
        _point(lat, lon),
        11132,
        start,
        end,
        cols=["precipitation"]
    )

    if df.empty:
        return pd.Series(
            dtype=float,
            index=pd.DatetimeIndex([], name="date"),
            name="precip_mm"
        )

    s = df["precipitation"] * 24 * df.index.days_in_month
    s.index = s.index.to_period("M").to_timestamp()

    # Construire un calendrier mensuel complet.
    monthly_index = pd.date_range(
        start=pd.Timestamp(start).to_period("M").to_timestamp(),
        end=(
            pd.Timestamp(end) - pd.Timedelta(days=1)
        ).to_period("M").to_timestamp(),
        freq="MS"
    )

    s = s.reindex(monthly_index)
    s.index.name = "date"

    return s.rename("precip_mm")


def fetch_gpm_monthly_status(start="2000-06-01", end=None) -> pd.DataFrame:
    """
    Récupère le statut des images GPM IMERG mensuelles.

    Valeurs possibles : permanent, provisional, mixed, unknown, no_data
    (voir classify_status).

    Convention : start inclus, end exclu (défaut : aujourd'hui, résolu ici).
    """
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    return _fetch_gpm_monthly_status(start, end)


@cached(ttl=GPM_CACHE_TTL_S)
def _fetch_gpm_monthly_status(start, end) -> pd.DataFrame:
    ee = _require_ee()

    ic = ee.ImageCollection(IMERG_MONTHLY)

    months = pd.date_range(
        start=start,
        end=end,
        freq="MS",
        inclusive="left"
    )

    rows = []

    for offset in range(0, len(months), 45):
        batch = months[offset:offset + 45]
        features = []

        for month in batch:
            date = month.strftime("%Y-%m-%d")

            start_month = ee.Date(date)
            end_month = start_month.advance(1, "month")

            sub = ic.filterDate(start_month, end_month)

            feature = ee.Feature(None, {
                "date": date,
                "statuses": sub.aggregate_array("status")
            })

            features.append(feature)

        result = ee.FeatureCollection(features).getInfo()

        for feature in result.get("features", []):
            props = feature.get("properties", {})
            status = classify_status(props.get("statuses"))

            rows.append({
                "date": props.get("date"),
                "status": status
            })

    if not rows:
        return pd.DataFrame(columns=["status"])

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])

    return df.set_index("date").sort_index()


# --------------------------------------------------------------------------- #
# 3. SMAP L4 (via GEE)
# --------------------------------------------------------------------------- #
# Collection et bandes vérifiées dans le catalogue GEE (NASA/SMAP/SPL4SMGP/008 : 3 h, pixel
# 11 km, sm_surface/sm_rootzone en fraction volumique, surface_temp en K, sm_rootzone_wetness 0-1).
SMAP_ID = "NASA/SMAP/SPL4SMGP/008"
SMAP_BANDS = ["sm_surface", "sm_rootzone", "surface_temp", "sm_rootzone_wetness"]


@cached()
def fetch_smap(lat, lon, start, end) -> pd.DataFrame:
    """Moyenne journalière : sm_surface (m3/m3, 0-5 cm), sm_rootzone (m3/m3, 0-100 cm),
    surface_temp (K), sm_rootzone_wetness (0-1, indicateur propre à SMAP).
    Convention : start inclus, end exclu. Moyenne des images 3-horaires disponibles du jour."""
    ee = _require_ee()
    ic = ee.ImageCollection(SMAP_ID).select(SMAP_BANDS)
    return _gee_daily(ic, _point(lat, lon), 11000, start, end, agg="mean", cols=SMAP_BANDS)


# --------------------------------------------------------------------------- #
# 4. MODIS  (via GEE) - facteurs d'échelle du PDF + masques qualité
# --------------------------------------------------------------------------- #
@cached()
def fetch_modis_vi(lat, lon, start, end, geometry=None) -> pd.DataFrame:
    """MOD13Q1 : NDVI, EVI (250 m / 16 j), x 0.0001. Masque SummaryQA <= 1 (bon/marginal)."""
    ee = _require_ee()
    ic = (ee.ImageCollection("MODIS/061/MOD13Q1")
          .map(lambda im: im.select(["NDVI", "EVI"])
               .updateMask(im.select("SummaryQA").lte(1))
               .copyProperties(im, ["system:time_start"])))
    return _gee_images(ic, _region(lat, lon, geometry, 250), 250, start, end,
                       cols=["NDVI", "EVI"]) * 0.0001


@cached()
def fetch_modis_reflectance(lat, lon, start, end, geometry=None) -> pd.DataFrame:
    """MOD09A1 (500 m / 8 j) : red=b01, nir=b02, blue=b03, swir=b06, x 0.0001.
    Masque StateQA : ni nuage (bits 0-1) ni ombre de nuage (bit 2)."""
    ee = _require_ee()
    bands = ["sur_refl_b01", "sur_refl_b02", "sur_refl_b03", "sur_refl_b06"]

    def qc(im):
        st = im.select("StateQA")
        ok = st.bitwiseAnd(3).eq(0).And(st.bitwiseAnd(4).eq(0))
        return im.select(bands).updateMask(ok).copyProperties(im, ["system:time_start"])

    ic = ee.ImageCollection("MODIS/061/MOD09A1").map(qc)
    df = _gee_images(ic, _region(lat, lon, geometry, 500), 500, start, end, cols=bands) * 0.0001
    return df.rename(columns=dict(zip(bands, ["red", "nir", "blue", "swir"])))


@cached()
def fetch_modis_lst(lat, lon, start, end, geometry=None) -> pd.DataFrame:
    """MOD11A2 (1 km / 8 j) : LST_Day_1km, LST_Night_1km en °C (x0.02 - 273.15).
    Masque QC (bits 0-1 <= 1 : LST produite)."""
    ee = _require_ee()

    def qc(im):
        day = im.select("LST_Day_1km").updateMask(im.select("QC_Day").bitwiseAnd(3).lte(1))
        night = im.select("LST_Night_1km").updateMask(im.select("QC_Night").bitwiseAnd(3).lte(1))
        return day.addBands(night).copyProperties(im, ["system:time_start"])

    ic = ee.ImageCollection("MODIS/061/MOD11A2").map(qc)
    cols = ["LST_Day_1km", "LST_Night_1km"]
    return _gee_images(ic, _region(lat, lon, geometry, 1000), 1000, start, end,
                       cols=cols) * 0.02 - 273.15


@cached()
def fetch_modis_lst_bounds(lat, lon, start, end, radius_km=10) -> pd.DataFrame:
    """Percentiles 5 et 95 de LST_Day dans un rayon autour du champ, par date
    (approximation de LST_min et LST_max pour le TVDI)."""
    ee = _require_ee()
    region = _point(lat, lon).buffer(radius_km * 1000)
    ic = (ee.ImageCollection("MODIS/061/MOD11A2")
          .map(lambda im: im.select("LST_Day_1km")
               .updateMask(im.select("QC_Day").bitwiseAnd(3).lte(1))
               .copyProperties(im, ["system:time_start"])))
    cols = ["LST_Day_1km_p5", "LST_Day_1km_p95"]
    df = _gee_images(ic, region, 1000, start, end, ee.Reducer.percentile([5, 95]), cols=cols)
    df = df * 0.02 - 273.15
    return df.rename(columns={"LST_Day_1km_p5": "lst_min", "LST_Day_1km_p95": "lst_max"})


@cached()
def fetch_modis_et(lat, lon, start, end, geometry=None) -> pd.DataFrame:
    """MOD16A2 (500 m / 8 j) : ET, PET en mm/8 j (x0.1). Masque ET_QC bit 0 = 0 (bonne qualité)."""
    ee = _require_ee()

    def qc(im):
        ok = im.select("ET_QC").bitwiseAnd(1).eq(0)
        return im.select(["ET", "PET"]).updateMask(ok).copyProperties(im, ["system:time_start"])

    ic = ee.ImageCollection("MODIS/061/MOD16A2").map(qc)
    return _gee_images(ic, _region(lat, lon, geometry, 500), 500, start, end,
                       cols=["ET", "PET"]) * 0.1


# --------------------------------------------------------------------------- #
# 5. SRTM  (via GEE)
# --------------------------------------------------------------------------- #
@cached(ttl=365 * 24 * 3600)
def fetch_dem_patch(lat, lon, half_size_m=1500) -> np.ndarray:
    """Matrice d'altitudes SRTM 30 m (m) centrée sur le point (~100x100 pixels)."""
    ee = _require_ee()
    region = _point(lat, lon).buffer(half_size_m).bounds()
    arr = (ee.Image("USGS/SRTMGL1_003").select("elevation")
           .sampleRectangle(region=region, defaultValue=0).get("elevation").getInfo())
    return np.array(arr, dtype=float)


@cached(ttl=365 * 24 * 3600)
def fetch_dem_zone(lat, lon, geometry, half_size_m=1500):
    """(dem, mask) : patch SRTM 30 m centré sur le centroïde + masque booléen des pixels
    dont le centre est dans la parcelle (même grille que le dem)."""
    ee = _require_ee()
    region = _point(lat, lon).buffer(half_size_m).bounds()
    srtm = ee.Image("USGS/SRTMGL1_003").select("elevation")
    poly = ee.Geometry(normalize_polygon(geometry), None, False)
    zone = (ee.Image.constant(1).clip(poly).unmask(0)
            .reproject(srtm.projection()).rename("zone"))
    props = srtm.addBands(zone).sampleRectangle(region=region, defaultValue=0).getInfo()["properties"]
    return np.array(props["elevation"], dtype=float), np.array(props["zone"]) > 0


@cached(ttl=365 * 24 * 3600)
def fetch_upstream_area_km2(lat, lon) -> float | None:
    """Aire drainée amont (km2) depuis MERIT Hydro (nécessaire au TWI)."""
    ee = _require_ee()
    v = (ee.Image("MERIT/Hydro/v1_0_1").select("upa")
         .reduceRegion(ee.Reducer.first(), _point(lat, lon), 90).get("upa").getInfo())
    return v


# --------------------------------------------------------------------------- #
# 6. SoilGrids (REST ISRIC)
# --------------------------------------------------------------------------- #
SG_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
SG_PROPS = ["clay", "sand", "silt", "bdod", "soc", "nitrogen", "phh2o"]
SG_DEPTHS = {"0-5cm": (0, 5), "5-15cm": (5, 15), "15-30cm": (15, 30),
             "30-60cm": (30, 60), "60-100cm": (60, 100)}


@cached(ttl=365 * 24 * 3600)
def fetch_soilgrids(lat, lon) -> pd.DataFrame:
    """Profil du sol : lignes = profondeurs, colonnes = propriétés, en unités lisibles
    (clay/sand/silt en %, bdod en g/cm3, soc et nitrogen en g/kg, phh2o en pH)."""
    js = _get(SG_URL, {"lon": lon, "lat": lat, "property": SG_PROPS,
                       "depth": list(SG_DEPTHS), "value": "mean"})
    data = {}
    for layer in js["properties"]["layers"]:
        d = layer["unit_measure"]["d_factor"]           # facteur de conversion ISRIC
        data[layer["name"]] = {
            dep["label"]: (np.nan if dep["values"].get("mean") is None
                           else dep["values"]["mean"] / d)
            for dep in layer["depths"]}
    return pd.DataFrame(data).reindex(list(SG_DEPTHS))


def soil_profile_mean(profile: pd.DataFrame, zr_cm: float = 100) -> pd.Series:
    """Moyenne pondérée par l'épaisseur sur la profondeur racinaire [0, zr_cm]."""
    w = pd.Series({k: max(0, min(b, zr_cm) - min(a, zr_cm)) for k, (a, b) in SG_DEPTHS.items()})
    out = {}
    for c in profile:
        ok = profile[c].notna() & (w > 0)
        out[c] = float((profile[c][ok] * w[ok]).sum() / w[ok].sum()) if ok.any() else np.nan
    return pd.Series(out)
