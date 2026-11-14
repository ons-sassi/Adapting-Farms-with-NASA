"""Test hors ligne : les SATELLITES sont simulés (pas de réseau), mais le catalogue de cultures
est réel : lu dans MySQL si TEST_MYSQL=1 (après `python bd/connection.py`), sinon dans le même CSV
que celui chargé en base."""
import json, numpy as np, pandas as pd, tempfile
from common import connectors as cn
cn.CACHE_DIR = __import__("pathlib").Path(tempfile.mkdtemp())
from indicateurs_service import indicateurs as ind
import os
from bd import cultures
if not os.getenv("TEST_MYSQL"):
    cultures._lire_table = lambda: cultures.lire_csv(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "bd", "data", "cultures_completes_8_especes_v6.csv"))

rng = np.random.default_rng(0)
def days(s, e): return pd.date_range(s, e, freq="D", name="date")

def power(lat, lon, s, e, parameters=None):
    d = days(s, e); n = len(d); doy = d.dayofyear.values
    t = 18 + 10*np.sin(2*np.pi*(doy-110)/365)
    cols = dict(T2M_MAX=t+6, T2M_MIN=t-6+rng.normal(0,1,n), T2M=t, PRECTOTCORR=rng.gamma(0.3,4,n),
                ALLSKY_SFC_SW_DWN=15+8*np.sin(2*np.pi*(doy-80)/365), RH2M=rng.uniform(40,80,n),
                WS2M=rng.uniform(1,4,n), T2MDEW=t-8)
    df = pd.DataFrame(cols, index=d)
    if parameters: df = df[parameters]
    df.attrs["elevation"] = 80.0
    return df
cn.fetch_power = power
cn.last_available = lambda c: "2026-12-31" if "SMAP" in c else "2026-03-31"
def gpm(lat, lon, s, e):
    d = days(s, e); return pd.DataFrame({"precip_mm": rng.gamma(0.2, 5, len(d))}, index=d)
cn.fetch_gpm_daily = gpm
def gpm_m(lat, lon, **k):
    idx = pd.date_range("2000-06-01", "2026-02-01", freq="MS")
    m = idx.month.values
    return pd.Series(rng.gamma(2, 15, len(idx))*(1+np.cos(2*np.pi*(m-1)/12)), index=idx, name="precip_mm")
cn.fetch_gpm_monthly = gpm_m
# statuts de publication IMERG (simulés) : jours/mois `permanent`
cn.fetch_gpm_daily_status = lambda s, e: pd.DataFrame(
    {"status": "permanent"}, index=pd.date_range(s, e, freq="D", inclusive="left", name="date"))
cn.fetch_gpm_monthly_status = lambda start="2000-06-01", end=None: pd.DataFrame(
    {"status": "permanent"}, index=pd.date_range(start, end, freq="MS", inclusive="left", name="date"))
def smap(lat, lon, s, e):
    d = days(s, e); n=len(d)
    return pd.DataFrame(dict(sm_surface=rng.uniform(.05,.35,n), sm_rootzone=rng.uniform(.1,.3,n),
        surface_temp=rng.uniform(275,300,n), sm_rootzone_wetness=rng.uniform(.2,.7,n)), index=d)
cn.fetch_smap = smap
def refl(lat, lon, s, e, geometry=None):
    d = pd.date_range(s, e, freq="8D", name="date"); n=len(d)
    return pd.DataFrame(dict(red=rng.uniform(.03,.2,n), nir=rng.uniform(.2,.5,n), blue=rng.uniform(.02,.1,n), swir=rng.uniform(.1,.3,n)), index=d)
cn.fetch_modis_reflectance = refl
def vi(lat, lon, s, e, geometry=None):
    d = pd.date_range(s, e, freq="16D", name="date"); return pd.DataFrame(dict(NDVI=rng.uniform(.1,.8,len(d)), EVI=rng.uniform(.1,.6,len(d))), index=d)
cn.fetch_modis_vi = vi
def lst(lat, lon, s, e, geometry=None):
    d = pd.date_range(s, e, freq="8D", name="date"); n=len(d)
    return pd.DataFrame(dict(LST_Day_1km=rng.uniform(15,45,n), LST_Night_1km=rng.uniform(2,20,n)), index=d)
cn.fetch_modis_lst = lst
def bnd(lat, lon, s, e):
    d = pd.date_range(s, e, freq="8D", name="date"); n=len(d)
    return pd.DataFrame(dict(lst_min=rng.uniform(15,25,n), lst_max=rng.uniform(40,50,n)), index=d)
cn.fetch_modis_lst_bounds = bnd
def et(lat, lon, s, e, geometry=None):
    d = pd.date_range(s, e, freq="8D", name="date"); n=len(d)
    return pd.DataFrame(dict(ET=rng.uniform(2,20,n), PET=rng.uniform(15,40,n)), index=d)
cn.fetch_modis_et = et
def sg(lat, lon):
    return pd.DataFrame(dict(clay=[30]*5, sand=[35]*5, silt=[35]*5, bdod=[1.35]*5, soc=[10,9,8,6,5], nitrogen=[1.0,.9,.8,.6,.5], phh2o=[7.8]*5), index=list(cn.SG_DEPTHS))
cn.fetch_soilgrids = sg
yy, xx = np.mgrid[0:101, 0:101]
cn.fetch_dem_patch = lambda lat, lon, **k: 200 + 0.03*xx*30*0.05 + 0.02*yy + rng.normal(0,.2,(101,101))
cn.fetch_upstream_area_km2 = lambda lat, lon: 1.5

r = ind.get_indicateurs({"lat": 35.68, "lon": 10.10, "surface_ha": 5}, "blé")
txt = json.dumps(r, ensure_ascii=False, indent=1)
print(r["periode"], r["statut_sol"])
assert r["culture"]["code"] == 2114 and r["culture"]["source"].startswith("MySQL")
assert r["culture"]["gdd_requis"] == 2400 and r["culture"]["zr_mm"] == 1800     # valeurs de la base, pas du code
assert any("dérivée" in w for w in r["avertissements"])
for b, v in r["indicateurs"].items(): print(b, len(v), list(v)[:6])
print("ERREURS:", r["erreurs"])
for w in r["avertissements"]: print("-", w)
print(r["indicateurs"]["power"]["Last_Spring_Frost"], r["indicateurs"]["power"]["Ratio_GDD"])
print(r["indicateurs"]["smap"]["RSM_hors_plage_pct"]["valeur"], r["indicateurs"]["srtm"]["slope_pct"]["valeur"])

# sol mesuré complet
r2 = ind.get_indicateurs({"lat": 35.68, "lon": 10.10, "sol_mesure": dict(sand=20, clay=45, soc=8, nitrogen=.8, phh2o=7.9, bdod=1.3)}, "orge")
print(r2["statut_sol"], r2["periode"], r2["erreurs"])

# cache
calls = []
@cn.cached()
def f(x): calls.append(x); return pd.DataFrame({"a":[x]})
f(1); f(1); print("cache calls:", calls)


# ------------------------- service zonal -------------------------------------
from zonal_service import zonal
poly = {"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[10.100,35.680],[10.104,35.680],[10.104,35.683],[10.100,35.683],[10.100,35.680]]]}}
lat_c, lon_c = cn.poly_centroid(poly); ha = cn.poly_area_m2(cn.normalize_polygon(poly))/1e4
print("centroide", round(lat_c,5), round(lon_c,5), "surface ha", round(ha,2))
assert abs(lat_c-35.6815)<1e-4 and abs(lon_c-10.102)<1e-4 and 10 < ha < 15
pts = cn.points_in_polygon(poly, 4); print("points sol", len(pts)); assert 1 <= len(pts) <= 4

calls = {"dem_zone": 0}
def dem_zone(lat, lon, geometry, half_size_m=1500):
    calls["dem_zone"] += 1
    m = np.zeros((101,101), bool); m[40:60, 40:62] = True
    return cn.fetch_dem_patch(lat, lon), m
cn.fetch_dem_zone = dem_zone
dz = zonal.get_donnees_zonales(poly, "2025-10-15", "2026-06-15", soil_sleep_s=0)
print("zonal cles:", sorted(k for k in dz if k not in ("geometry",)))
print("meta:", dz["meta"], "erreurs:", dz["erreurs"])
assert not dz["erreurs"] and dz["meta"]["srtm_pixels"] == 20*22

r3 = ind.get_indicateurs({"surface_ha": None}, "blé", donnees=dz)   # pas de lat/lon : centroide injecté
print(r3["parcelle"], r3["periode"], r3["erreurs"])
print("srtm note:", r3["indicateurs"]["srtm"]["slope_pct"])
assert r3["parcelle"]["donnees_zonales"] and r3["parcelle"]["surface_ha"] == dz["surface_ha"]
assert "moyenne sur 440 pixel" in r3["indicateurs"]["srtm"]["slope_pct"]["note"]
assert r3["indicateurs"]["modis"] and not r3["erreurs"]

# repli : bloc zonal manquant -> lecture au point
dz2 = dict(dz); dz2.pop("dem"); dz2["erreurs"] = {"dem": "RuntimeError: test"}; dz2["avertissements"] = ["Données zonales « dem » indisponibles"]
r4 = ind.get_indicateurs({}, "blé", donnees=dz2)
print("repli srtm:", r4["indicateurs"]["srtm"]["slope_pct"]["note"]); assert "pixel central" in r4["indicateurs"]["srtm"]["slope_pct"]["note"]
# période incohérente
try: ind.get_indicateurs({}, "blé", "2024-01-01", "2024-06-01", donnees=dz); print("ERREUR attendue")
except ValueError as e: print("OK période:", str(e)[:60])
# ------------------------- transport JSON entre les deux services -------------
import json as _json
from zonal_service import donnees_to_json, donnees_from_json
payload = _json.dumps(donnees_to_json(dz), allow_nan=False)      # JSON strict : pas de NaN
dz_rt = donnees_from_json(_json.loads(payload))
assert dz_rt["centroide"] == dz["centroide"] and (dz_rt["dem_mask"] == dz["dem_mask"]).all()
assert dz_rt["modis_refl"].shape == dz["modis_refl"].shape and dz_rt["modis_refl"].index.equals(dz["modis_refl"].index)
r5 = ind.get_indicateurs({}, "blé", donnees=dz_rt)
assert r5["indicateurs"]["srtm"]["slope_pct"]["valeur"] == r3["indicateurs"]["srtm"]["slope_pct"]["valeur"]
assert r5["indicateurs"]["modis"]["NDVI_mean"]["valeur"] == r3["indicateurs"]["modis"]["NDVI_mean"]["valeur"]
print("JSON roundtrip OK,", len(payload)//1024, "ko")
print("ALL OK")
