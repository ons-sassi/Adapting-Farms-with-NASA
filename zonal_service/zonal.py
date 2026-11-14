"""
zonal.py : service « données zonales » d'une parcelle (polygone GeoJSON).

    donnees = get_donnees_zonales(geometry, start, end)
    res = get_indicateurs(parcelle, "blé", donnees=donnees)

Ce service ne calcule AUCUN indice : il renvoie des données brutes (séries MODIS moyennées sur
le polygone, MNT + masque de la parcelle, profil SoilGrids moyenné sur plusieurs points).
Les indices restent calculés dans indices.py / indicateurs.py (pas de duplication).

Pour POWER, SMAP et IMERG (pixels >= 11 km), le polygone ne change rien : on utilise le
centroïde, renvoyé dans donnees["centroide"].

Un polygone plus petit qu'un pixel est remplacé par le point central pour ce produit
(meta["modis"][produit] l'indique), car une moyenne zonale y serait vide ou trompeuse.
Un bloc qui échoue est listé dans donnees["erreurs"] ; get_indicateurs retombe alors sur la
lecture au point pour ce bloc.
"""
from __future__ import annotations

import time

import pandas as pd

from common import connectors as cn

MODIS_ECHELLES = {"modis_refl": 500, "modis_vi_hist": 250, "modis_lst": 1000, "modis_et": 500}
SOILGRIDS_PIXEL_M = 250


def get_donnees_zonales(geometry: dict, start: str, end: str,
                        soil_points: int = 4, soil_sleep_s: float = 12.0) -> dict:
    """geometry : GeoJSON (Polygon, Feature...), coordonnées [lon, lat].
    soil_sleep_s : pause entre deux points SoilGrids (limite ~5 requêtes/min)."""
    g = cn.normalize_polygon(geometry)
    lat, lon = cn.poly_centroid(g)
    lat, lon = round(lat, 4), round(lon, 4)
    aire_m2 = cn.poly_area_m2(g)

    out = {"geometry": g, "centroide": (lat, lon), "surface_ha": round(aire_m2 / 1e4, 3),
           "periode": (start, end), "erreurs": {}, "avertissements": [],
           "meta": {"modis": {}}}

    def tenter(cle, f):
        try:
            out[cle] = f()
        except Exception as e:
            out["erreurs"][cle] = f"{type(e).__name__}: {e}"

    # --- MODIS : moyenne sur le polygone (ou point si parcelle < 1 pixel) ------------ #
    for cle, scale in MODIS_ECHELLES.items():
        out["meta"]["modis"][cle] = ("zonale (polygone)" if aire_m2 >= scale ** 2
                                     else "point central (parcelle plus petite qu'un pixel)")
    tenter("modis_refl", lambda: cn.fetch_modis_reflectance(lat, lon, start, end, geometry=g))
    tenter("modis_vi_hist", lambda: cn.fetch_modis_vi(lat, lon, "2000-02-18", end, geometry=g))
    tenter("modis_lst", lambda: cn.fetch_modis_lst(lat, lon, start, end, geometry=g))
    tenter("modis_et", lambda: cn.fetch_modis_et(lat, lon, start, end, geometry=g))
    # bornes TVDI : toujours autour du centroïde (rayon 10 km)
    tenter("modis_lst_bounds", lambda: cn.fetch_modis_lst_bounds(lat, lon, start, end))

    # --- SRTM : MNT + masque de la parcelle ----------------------------------------- #
    def dem():
        d, m = cn.fetch_dem_zone(lat, lon, g)
        out["dem_mask"] = m
        out["meta"]["srtm_pixels"] = int(m.sum())
        return d
    tenter("dem", dem)
    tenter("upa", lambda: cn.fetch_upstream_area_km2(lat, lon))

    # --- SoilGrids : plusieurs points si la parcelle couvre plusieurs pixels ---------- #
    def sol():
        pts = (cn.points_in_polygon(g, soil_points)
               if aire_m2 >= (2 * SOILGRIDS_PIXEL_M) ** 2 else [(lat, lon)])
        profils = []
        for i, (la, lo) in enumerate(pts):
            if i and soil_sleep_s:
                time.sleep(soil_sleep_s)
            profils.append(cn.fetch_soilgrids(round(la, 4), round(lo, 4)))
        out["meta"]["soilgrids_points"] = len(profils)
        if len(profils) == 1:
            return profils[0]
        return pd.concat(profils).groupby(level=0).mean().reindex(list(cn.SG_DEPTHS))
    tenter("sol", sol)

    for cle, msg in out["erreurs"].items():
        out["avertissements"].append(f"Données zonales « {cle} » indisponibles ({msg}) : "
                                     "lecture au point utilisée à la place.")
    return out
