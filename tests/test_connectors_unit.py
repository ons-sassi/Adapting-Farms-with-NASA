"""Tests unitaires de common/connectors.py. Les appels réseau / GEE sont SIMULÉS : ces tests
vérifient la logique locale (conversions, statuts, calendrier, cache), pas les serveurs."""
import os
import time
import warnings
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from common import connectors as cn
from indicateurs_service import indicateurs as ind


@pytest.fixture
def ee_stub(monkeypatch):
    stub = MagicMock(name="ee")
    monkeypatch.setattr(cn, "_ee", stub)
    return stub


# ------------------------------- statuts ------------------------------------ #
@pytest.mark.parametrize("valeurs, attendu", [
    (None, "no_data"), ([], "no_data"),
    (["permanent"] * 48, "permanent"),
    (["provisional"] * 3, "provisional"),
    (["permanent", "provisional", "permanent"], "mixed"),
    (["permanent", "autre"], "unknown"),
    (["early"], "unknown"),
])
def test_classify_status(valeurs, attendu):
    assert cn.classify_status(valeurs) == attendu


def serie_statuts(valeurs, start="2025-01-01", freq="D"):
    return pd.DataFrame({"status": valeurs},
                        index=pd.date_range(start, periods=len(valeurs), freq=freq))


def test_resume_statut_produit():
    r = ind._resume_statut_produit
    dates = pd.date_range("2025-01-01", periods=3, freq="D")
    assert r(serie_statuts(["permanent"] * 3), dates) == "permanent"
    assert r(serie_statuts(["provisional"] * 3), dates) == "provisional"
    assert r(serie_statuts(["permanent", "provisional", "provisional"]), dates) == "mixed"
    assert r(serie_statuts(["permanent", "mixed", "permanent"]), dates) == "mixed"
    assert r(serie_statuts(["no_data"] * 3), dates) == "no_data"
    assert r(serie_statuts(["permanent", "unknown", "permanent"]), dates) == "unknown"
    assert r(serie_statuts(["permanent", "no_data", "permanent"]), dates) == "incomplete"
    assert r(serie_statuts(["permanent"] * 2), dates) == "incomplete"   # une date absente
    assert r(None, dates) == "unknown"
    assert r(pd.DataFrame(columns=["status"]), dates) == "unknown"
    assert r(serie_statuts(["permanent"] * 3), pd.DatetimeIndex([])) == "unknown"


# ------------------------------- _rows_to_df -------------------------------- #
def test_rows_to_df_vide_garde_les_colonnes():
    df = cn._rows_to_df([], ["a", "b"])
    assert list(df.columns) == ["a", "b"] and df.empty and isinstance(df.index, pd.DatetimeIndex)


def test_rows_to_df_colonne_entierement_vide_est_float():
    rows = [{"date": "2025-01-02", "x": None, "y": 1}, {"date": "2025-01-01", "x": None, "y": 2}]
    df = cn._rows_to_df(rows, ["x", "y"])
    assert df["x"].dtype == float and df["x"].isna().all()
    assert df.index.is_monotonic_increasing
    assert (df["x"] * 2).isna().all()          # opérations arithmétiques possibles


def test_rows_to_df_colonne_absente_devient_nan():
    df = cn._rows_to_df([{"date": "2025-01-01", "y": 1}], ["x", "y"])
    assert np.isnan(df.loc["2025-01-01", "x"])


# ------------------------------- GPM mensuel -------------------------------- #
def test_gpm_mensuel_conversion_mmh_vers_mm_et_mois_manquants(monkeypatch, ee_stub):
    """mm/h moyen x 24 x jours du mois ; mois sans image conservé en NaN ; calendrier complet."""
    taux = pd.DataFrame({"precipitation": [0.10, 0.05, 0.20]},
                        index=pd.to_datetime(["2025-01-01", "2025-02-01", "2025-04-01"]))
    monkeypatch.setattr(cn, "_gee_images", lambda *a, **k: taux)
    s = cn.fetch_gpm_monthly(35.68, 10.10, "2025-01-01", "2025-05-01")
    assert list(s.index) == list(pd.date_range("2025-01-01", "2025-04-01", freq="MS"))
    assert s["2025-01-01"] == pytest.approx(0.10 * 24 * 31)
    assert s["2025-02-01"] == pytest.approx(0.05 * 24 * 28)
    assert np.isnan(s["2025-03-01"])                     # mois manquant conservé
    assert s["2025-04-01"] == pytest.approx(0.20 * 24 * 30)
    assert s.name == "precip_mm"


def test_gpm_mensuel_aucune_image(monkeypatch, ee_stub):
    monkeypatch.setattr(cn, "_gee_images", lambda *a, **k: cn._empty(["precipitation"]))
    s = cn.fetch_gpm_monthly(35.68, 10.10, "2025-01-01", "2025-03-01")
    assert s.empty and s.name == "precip_mm"


def test_gpm_mensuel_end_par_defaut_est_resolu_avant_le_cache(monkeypatch):
    vus = []
    monkeypatch.setattr(cn, "_fetch_gpm_monthly", lambda lat, lon, start, end: vus.append(end))
    monkeypatch.setattr(cn, "_fetch_gpm_monthly_status", lambda start, end: vus.append(end))
    cn.fetch_gpm_monthly(1, 2)
    cn.fetch_gpm_monthly_status()
    today = pd.Timestamp.today().strftime("%Y-%m-%d")
    assert vus == [today, today]


def test_statuts_mensuels_et_quotidiens_assembles(ee_stub):
    ee_stub.FeatureCollection.return_value.getInfo.return_value = {"features": [
        {"properties": {"date": "2025-01-01", "statuses": ["permanent"]}},
        {"properties": {"date": "2025-02-01", "statuses": ["provisional"]}},
        {"properties": {"date": "2025-03-01", "statuses": []}},
    ]}
    m = cn.fetch_gpm_monthly_status("2025-01-01", "2025-04-01")
    assert m["status"].tolist() == ["permanent", "provisional", "no_data"]
    assert m.index.tolist() == list(pd.date_range("2025-01-01", periods=3, freq="MS"))
    ee_stub.FeatureCollection.return_value.getInfo.return_value = {"features": [
        {"properties": {"date": "2025-01-02", "statuses": ["permanent", "provisional"]}},
        {"properties": {"date": "2025-01-01", "statuses": ["x"]}},
    ]}
    d = cn.fetch_gpm_daily_status("2025-01-01", "2025-01-03")
    assert d["status"].tolist() == ["unknown", "mixed"] and d.index.is_monotonic_increasing


def test_gee_daily_garde_fous(ee_stub):
    with pytest.raises(ValueError):
        cn._gee_daily(MagicMock(), None, 1, "2025-01-01", "2025-01-03", agg="median")
    with pytest.raises(ValueError):
        cn._gee_daily(MagicMock(), None, 1, "2025-01-01", "2025-01-03", chunk=0)
    vide = cn._gee_daily(MagicMock(), None, 1, "2025-01-03", "2025-01-03", cols=["precipitation"])
    assert vide.empty and list(vide.columns) == ["precipitation"]      # start == end : rien (end exclu)


def test_gee_daily_jour_invalide_reste_nan(ee_stub):
    """Un jour sans cumul valide (propriété absente côté GEE) devient NaN, jamais 0."""
    ee_stub.FeatureCollection.return_value.getInfo.return_value = {"features": [
        {"properties": {"date": "2025-01-01", "precipitation": 2.5}},
        {"properties": {"date": "2025-01-02"}},                       # < 48 images : pas de valeur
    ]}
    df = cn._gee_daily(MagicMock(), None, 1, "2025-01-01", "2025-01-03", agg="sum",
                       cols=["precipitation"])
    assert df["precipitation"].iloc[0] == 2.5 and np.isnan(df["precipitation"].iloc[1])


# ------------------------------- POWER -------------------------------------- #
def test_power_conversion_valeurs_manquantes(monkeypatch):
    vu = {}
    def faux_get(url, params=None, **k):
        vu.update(params)
        return {"properties": {"parameter": {
                    "T2M": {"20250101": 10.0, "20250102": -999.0},
                    "PRECTOTCORR": {"20250101": 0.0, "20250102": 3.2}}},
                "geometry": {"coordinates": [10.1, 35.68, 81.5]}}
    monkeypatch.setattr(cn, "_get", faux_get)
    df = cn.fetch_power(35.68, 10.1, "2025-01-01", "2025-01-02", parameters=["T2M", "PRECTOTCORR"])
    assert vu["start"] == "20250101" and vu["end"] == "20250102"
    assert np.isnan(df.loc["2025-01-02", "T2M"]) and df.loc["2025-01-02", "PRECTOTCORR"] == 3.2
    assert df.attrs["elevation"] == 81.5 and df.index.name == "date"


def test_power_reponse_inattendue(monkeypatch):
    monkeypatch.setattr(cn, "_get", lambda *a, **k: {"messages": ["erreur"]})
    with pytest.raises(RuntimeError, match="POWER"):
        cn.fetch_power(1, 2, "2025-01-01", "2025-01-02")


# ------------------------------- SoilGrids ---------------------------------- #
def test_soilgrids_conversions_d_factor(monkeypatch):
    def couche(nom, d, v):
        return {"name": nom, "unit_measure": {"d_factor": d},
                "depths": [{"label": "0-5cm", "values": {"mean": v}},
                           {"label": "5-15cm", "values": {"mean": None}}]}
    monkeypatch.setattr(cn, "_get", lambda *a, **k: {"properties": {"layers": [
        couche("clay", 10, 300), couche("bdod", 100, 135), couche("phh2o", 10, 78),
        couche("soc", 10, 95), couche("nitrogen", 100, 90)]}})
    df = cn.fetch_soilgrids(35.68, 10.1)
    assert df.loc["0-5cm", "clay"] == pytest.approx(30.0)        # g/kg -> %
    assert df.loc["0-5cm", "bdod"] == pytest.approx(1.35)        # cg/cm3 -> g/cm3
    assert df.loc["0-5cm", "phh2o"] == pytest.approx(7.8)
    assert df.loc["0-5cm", "soc"] == pytest.approx(9.5)          # dg/kg -> g/kg
    assert df.loc["0-5cm", "nitrogen"] == pytest.approx(0.9)     # cg/kg -> g/kg
    assert np.isnan(df.loc["5-15cm", "clay"])                    # valeur nulle -> NaN
    assert list(df.index) == list(cn.SG_DEPTHS)


def test_soil_profile_mean_ponderee():
    prof = pd.DataFrame({"clay": [10, 20, 30, 40, 50]}, index=list(cn.SG_DEPTHS), dtype=float)
    # 0-30 cm : (10*5 + 20*10 + 30*15) / 30 = 23.33
    assert cn.soil_profile_mean(prof, 30)["clay"] == pytest.approx((10 * 5 + 20 * 10 + 30 * 15) / 30)
    prof.loc["5-15cm", "clay"] = np.nan
    assert cn.soil_profile_mean(prof, 30)["clay"] == pytest.approx((10 * 5 + 30 * 15) / 20)


# ------------------------------- cache -------------------------------------- #
def test_cache_hit_miss_et_cles():
    appels = []
    @cn.cached()
    def f(x, y=0):
        appels.append((x, y)); return pd.DataFrame({"a": [x + y]})
    f(1); f(1); f(2); f(1, y=1)
    assert appels == [(1, 0), (2, 0), (1, 1)]


def test_cache_ttl_expire():
    appels = []
    @cn.cached(ttl=1)
    def f(): appels.append(1); return pd.Series([1.0])
    f()
    for p in cn.CACHE_DIR.glob("*.pkl"):
        os.utime(p, (time.time() - 10, time.time() - 10))
    f()
    assert len(appels) == 2


def test_cache_corrompu_recalcule_avec_avertissement():
    appels = []
    @cn.cached()
    def f(): appels.append(1); return pd.Series([1.0])
    f()
    for p in cn.CACHE_DIR.glob("*.pkl"):
        p.write_bytes(b"pas un pickle")
    with pytest.warns(RuntimeWarning, match="Cache illisible"):
        assert f().iloc[0] == 1.0
    assert len(appels) == 2


def test_cache_ne_stocke_pas_none():
    appels = []
    @cn.cached()
    def f(): appels.append(1); return None
    f(); f()
    assert len(appels) == 2


def test_gpm_ttl_court():
    assert cn.GPM_CACHE_TTL_S <= 24 * 3600 < cn.CACHE_TTL_S


# ------------------------------- GEE init ----------------------------------- #
def test_init_gee_validations():
    with pytest.raises(ValueError):
        cn.init_gee("")
    with pytest.raises(ValueError, match="ensemble"):
        cn.init_gee("p", service_account="a@b.iam", key_file=None)


def test_require_ee_sans_init(monkeypatch):
    monkeypatch.setattr(cn, "_ee", None)
    with pytest.raises(RuntimeError, match="init_gee"):
        cn.fetch_smap(1, 2, "2025-01-01", "2025-01-02")


def test_constantes_gee():
    assert cn.SMAP_ID == "NASA/SMAP/SPL4SMGP/008"
    assert set(cn.SMAP_BANDS) == {"sm_surface", "sm_rootzone", "surface_temp", "sm_rootzone_wetness"}
    assert cn.IMERG_HH == "NASA/GPM_L3/IMERG_V07" and cn.IMERG_MONTHLY == "NASA/GPM_L3/IMERG_MONTHLY_V07"
    assert cn.IMERG_HALFHOURS_PER_DAY == 48


# ------------------------------- géométrie ---------------------------------- #
CARRE = {"type": "Polygon", "coordinates": [[[10.0, 35.0], [10.01, 35.0], [10.01, 35.01],
                                              [10.0, 35.01], [10.0, 35.0]]]}


def test_geometrie_centroide_aire_points():
    lat, lon = cn.poly_centroid(CARRE)
    assert (lat, lon) == pytest.approx((35.005, 10.005))
    # 0.01° x 0.01° à 35°N ~ 1113 m x 911 m ~ 101 ha
    assert cn.poly_area_m2(CARRE) / 1e4 == pytest.approx(101.4, rel=0.02)
    pts = cn.points_in_polygon(CARRE, 4)
    assert 1 <= len(pts) <= 4 and all(35 < la < 35.01 and 10 < lo < 10.01 for la, lo in pts)


def test_geometrie_trou_et_multipolygone():
    trou = [[10.002, 35.002], [10.008, 35.002], [10.008, 35.008], [10.002, 35.008], [10.002, 35.002]]
    avec_trou = {"type": "Polygon", "coordinates": CARRE["coordinates"] + [trou]}
    assert cn.poly_area_m2(avec_trou) < cn.poly_area_m2(CARRE)
    multi = {"type": "MultiPolygon", "coordinates": [CARRE["coordinates"], CARRE["coordinates"]]}
    assert cn.poly_area_m2(multi) == pytest.approx(2 * cn.poly_area_m2(CARRE))
    feat = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": CARRE}]}
    assert cn.normalize_polygon(feat)["type"] == "Polygon"


@pytest.mark.parametrize("bad", [
    [], {"type": "Point", "coordinates": [1, 2]},
    {"type": "Polygon", "coordinates": []},
    {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]},          # non fermé
    {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]][:0]},
    {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [np.nan, 1], [0, 0]]]},
])
def test_geometrie_invalide(bad):
    with pytest.raises(ValueError):
        cn.normalize_polygon(bad)
