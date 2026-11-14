"""Tests RÉELS Google Earth Engine. Ignorés automatiquement sans identifiants :

    set GEE_PROJECT=mon-projet-gcp           (et `earthengine authenticate` déjà fait)
    # ou, pour un compte de service : GEE_SERVICE_ACCOUNT=... GEE_KEY_FILE=chemin.json
    pytest -m gee -v

Référence : valeurs des exports réels du projet (point 35.6815 N / 10.102 E, janvier 2025 :
mensuel IMERG V07 = 61.752 mm ; cumul des 48 demi-heures/jour = 61.930 mm).
"""
import os

import numpy as np
import pandas as pd
import pytest

from common import connectors as cn

pytestmark = [pytest.mark.gee, pytest.mark.skipif(
    not os.environ.get("GEE_PROJECT"), reason="GEE_PROJECT non défini : test GEE réel ignoré")]

LAT, LON = 35.6815, 10.102


@pytest.fixture(scope="module", autouse=True)
def gee():
    cn.init_gee(os.environ["GEE_PROJECT"], os.environ.get("GEE_SERVICE_ACCOUNT"),
                os.environ.get("GEE_KEY_FILE"))


def test_last_available_format_et_ordre():
    d_hh, d_m, d_smap = (cn.last_available(c) for c in (cn.IMERG_HH, cn.IMERG_MONTHLY, cn.SMAP_ID))
    for d in (d_hh, d_m, d_smap):
        pd.Timestamp(d)
    assert pd.Timestamp(d_hh) >= pd.Timestamp(d_m)


def test_gpm_journalier_janvier_2025_48_images_et_valeurs_reelles():
    df = cn.fetch_gpm_daily(LAT, LON, "2025-01-01", "2025-02-01")
    assert len(df) == 31 and df["precip_mm"].notna().all() and (df["precip_mm"] >= 0).all()
    assert df["precip_mm"].sum() == pytest.approx(61.93, abs=0.2)


def test_gpm_mensuel_janvier_2025_valeur_reelle():
    s = cn.fetch_gpm_monthly(LAT, LON, "2025-01-01", "2025-03-01")
    assert list(s.index) == [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-02-01")]
    assert s.iloc[0] == pytest.approx(61.75, abs=0.2)


def test_gpm_journalier_vs_mensuel_coherents():
    d = cn.fetch_gpm_daily(LAT, LON, "2025-03-01", "2025-04-01")["precip_mm"].sum()
    m = cn.fetch_gpm_monthly(LAT, LON, "2025-03-01", "2025-04-01").iloc[0]
    assert abs(d - m) / m < 0.025


def test_statuts_publication():
    s = cn.fetch_gpm_daily_status("2025-09-25", "2025-10-05")
    assert set(s["status"]) <= {"permanent", "provisional", "mixed", "unknown", "no_data"}
    assert len(s) == 10


def test_smap_une_semaine():
    df = cn.fetch_smap(LAT, LON, "2025-01-01", "2025-01-08")
    assert list(df.columns) == cn.SMAP_BANDS and len(df) == 7
    assert df["sm_surface"].between(0, 0.6).all() and df["surface_temp"].between(250, 330).all()


def test_modis_ndvi_plage_physique():
    df = cn.fetch_modis_vi(LAT, LON, "2025-01-01", "2025-04-01")
    assert not df.empty and df["NDVI"].dropna().between(-0.2, 1).all()


def test_srtm_altitude_plausible():
    dem = cn.fetch_dem_patch(LAT, LON)
    assert dem.ndim == 2 and 0 < np.nanmedian(dem) < 500
