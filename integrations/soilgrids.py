import httpx

from integrations.errors import ExternalSourceError
from settings import settings

SOURCE_NAME = "SoilGrids (ISRIC)"
PROPERTIES = ["phh2o", "clay", "sand", "silt", "soc", "nitrogen", "bdod", "wv0033", "wv1500"]
DEPTHS = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}  # épaisseur (cm) pour la moyenne pondérée 0-30 cm

# Conversion des unités cibles SoilGrids vers les unités AgriSense.
TARGET_CONVERSION = {"wv0033": 0.01, "wv1500": 0.01}  # % volumique -> m3/m3


def fetch_topsoil(lat: float, lon: float) -> dict:
    params = [("lon", round(lon, 5)), ("lat", round(lat, 5)), ("value", "mean")]
    params += [("property", p) for p in PROPERTIES] + [("depth", d) for d in DEPTHS]
    try:
        response = httpx.get(settings.soilgrids_base_url, params=params, timeout=settings.http_timeout_seconds)
        response.raise_for_status()
        body = response.json()
    except httpx.HTTPError as exc:
        raise ExternalSourceError(SOURCE_NAME, f"requête impossible ({exc.__class__.__name__}) ; l'API bêta est parfois en pause") from exc
    except ValueError as exc:
        raise ExternalSourceError(SOURCE_NAME, "réponse non JSON") from exc
    return parse_properties_response(body)


def parse_properties_response(body: dict) -> dict:
    """Moyenne pondérée 0-30 cm de chaque propriété, convertie avec le d_factor fourni par l'API."""
    try:
        layers = body["properties"]["layers"]
    except (KeyError, TypeError) as exc:
        raise ExternalSourceError(SOURCE_NAME, "format de réponse inattendu") from exc
    values: dict[str, float | None] = {}
    for layer in layers:
        name = layer["name"]
        d_factor = layer.get("unit_measure", {}).get("d_factor", 1) or 1
        weighted, thickness = 0.0, 0
        for depth in layer.get("depths", []):
            mean = depth.get("values", {}).get("mean")
            label = depth.get("label")
            if mean is None or label not in DEPTHS:
                continue
            weighted += (mean / d_factor) * DEPTHS[label]
            thickness += DEPTHS[label]
        values[name] = round(weighted / thickness * TARGET_CONVERSION.get(name, 1), 4) if thickness else None
    return {
        "depth_label": "0-30 cm (moyenne pondérée)",
        "ph": values.get("phh2o"), "clay_pct": values.get("clay"), "sand_pct": values.get("sand"),
        "silt_pct": values.get("silt"), "soc_g_kg": values.get("soc"), "nitrogen_g_kg": values.get("nitrogen"),
        "bulk_density_g_cm3": values.get("bdod"), "theta_fc": values.get("wv0033"), "theta_pwp": values.get("wv1500"),
        "raw_payload": body,
    }
