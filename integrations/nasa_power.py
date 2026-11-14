import httpx

from integrations.errors import ExternalSourceError
from settings import settings

SOURCE_NAME = "NASA POWER"
REQUIRED_PARAMETERS = ["T2M_MAX", "T2M_MIN", "PRECTOTCORR"]
OPTIONAL_PARAMETERS = ["T2M", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN", "T2MDEW"]  # Penman-Monteith si présents
DAILY_PARAMETERS = REQUIRED_PARAMETERS + OPTIONAL_PARAMETERS
FILL_VALUE = -999.0


def fetch_daily_point(lat: float, lon: float, start: str, end: str) -> dict:
    """Série journalière (communauté AG) en un point. Dates au format YYYYMMDD.

    Retourne {"elevation_m", "dates": [...], "series": {param: [valeur ou None]}}.
    """
    params = {"parameters": ",".join(DAILY_PARAMETERS), "community": "AG", "longitude": round(lon, 4),
              "latitude": round(lat, 4), "start": start, "end": end, "format": "JSON"}
    try:
        response = httpx.get(settings.nasa_power_base_url, params=params, timeout=settings.http_timeout_seconds)
        response.raise_for_status()
        body = response.json()
    except httpx.HTTPError as exc:
        raise ExternalSourceError(SOURCE_NAME, f"requête impossible ({exc.__class__.__name__})") from exc
    except ValueError as exc:
        raise ExternalSourceError(SOURCE_NAME, "réponse non JSON") from exc
    return parse_daily_response(body)


def parse_daily_response(body: dict) -> dict:
    try:
        parameters = body["properties"]["parameter"]
        coordinates = body.get("geometry", {}).get("coordinates", [None, None, None])
    except (KeyError, TypeError) as exc:
        raise ExternalSourceError(SOURCE_NAME, "format de réponse inattendu") from exc
    missing = [p for p in REQUIRED_PARAMETERS if p not in parameters]
    if missing:
        raise ExternalSourceError(SOURCE_NAME, f"paramètres absents : {', '.join(missing)}")
    dates = sorted(parameters["T2M_MAX"].keys())
    series = {p: [None if parameters[p].get(d, FILL_VALUE) == FILL_VALUE else parameters[p][d] for d in dates]
              for p in DAILY_PARAMETERS if p in parameters}
    elevation = coordinates[2] if len(coordinates) > 2 else None
    return {"elevation_m": elevation, "dates": dates, "series": series}
