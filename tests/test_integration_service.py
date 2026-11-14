"""Tests d'intégration de get_indicateurs() : TOUTES les sources sont SIMULÉES (données
synthétiques déterministes) ; le catalogue de cultures est réel (CSV). Ils vérifient
l'enchaînement des blocs, les périodes, l'isolation des erreurs, les statuts, les NaN et la
sérialisation JSON. Ils ne disent RIEN sur la disponibilité réelle de GEE / POWER / SoilGrids."""
import json

import numpy as np
import pandas as pd
import pytest

from common import connectors as cn
from indicateurs_service import indicateurs as ind

START, END = "2025-10-15", "2026-06-12"
LAST_HH, LAST_MONTH, LAST_SMAP = "2026-03-31", "2026-02-01", "2026-03-31"
PARCELLE = {"lat": 35.68, "lon": 10.10, "surface_ha": 5}


class Sim:
    """Sources simulées + enregistrement des appels."""
    def __init__(self, monkeypatch):
        self.calls = {}
        self.nan_days = []                 # jours GPM forcés à NaN
        self.fail = set()                  # noms de fonctions cn qui lèvent une erreur
        self.daily_status = None           # fonction (date) -> statut
        self.rng = np.random.default_rng(42)
        mp = monkeypatch
        for name in ["fetch_power", "fetch_gpm_daily", "fetch_gpm_daily_status", "fetch_gpm_monthly",
                     "fetch_gpm_monthly_status", "fetch_smap", "fetch_modis_reflectance",
                     "fetch_modis_vi", "fetch_modis_lst", "fetch_modis_lst_bounds", "fetch_modis_et",
                     "fetch_soilgrids", "fetch_dem_patch", "fetch_upstream_area_km2"]:
            mp.setattr(cn, name, self._wrap(name, getattr(self, "_" + name)))
        mp.setattr(cn, "last_available", self._last_available)

    def _wrap(self, name, fn):
        def f(*a, **k):
            self.calls.setdefault(name, []).append((a, k))
            if name in self.fail:
                raise RuntimeError(f"{name} en panne (simulé)")
            return fn(*a, **k)
        return f

    @staticmethod
    def _last_available(cid):
        return {cn.IMERG_HH: LAST_HH, cn.IMERG_MONTHLY: LAST_MONTH}.get(cid, LAST_SMAP)

    def _fetch_power(self, lat, lon, s, e, parameters=None):       # e INCLUSIF (API POWER)
        d = pd.date_range(s, e, freq="D", name="date"); doy = d.dayofyear.values
        t = 18 + 10 * np.sin(2 * np.pi * (doy - 110) / 365)
        df = pd.DataFrame(dict(T2M_MAX=t + 6, T2M_MIN=t - 6, T2M=t, PRECTOTCORR=1.0 + 0 * t,
                               ALLSKY_SFC_SW_DWN=15 + 8 * np.sin(2 * np.pi * (doy - 80) / 365),
                               RH2M=60.0 + 0 * t, WS2M=2.5 + 0 * t, T2MDEW=t - 8), index=d)
        df = df[parameters] if parameters else df
        df.attrs["elevation"] = 80.0
        return df

    def _fetch_gpm_daily(self, lat, lon, s, e):                      # e EXCLU
        d = pd.date_range(s, e, freq="D", inclusive="left", name="date")
        v = np.where(np.arange(len(d)) % 5 == 0, 6.0, 0.0)           # 1 jour pluvieux sur 5
        v[10] = 25.0
        df = pd.DataFrame({"precip_mm": v.astype(float)}, index=d)
        for day in self.nan_days:
            if pd.Timestamp(day) in df.index:
                df.loc[pd.Timestamp(day), "precip_mm"] = np.nan
        return df

    def _fetch_gpm_daily_status(self, s, e):
        d = pd.date_range(s, e, freq="D", inclusive="left", name="date")
        f = self.daily_status or (lambda day: "permanent" if day <= pd.Timestamp("2025-09-30") else "provisional")
        return pd.DataFrame({"status": [f(x) for x in d]}, index=d)

    def _fetch_gpm_monthly(self, lat, lon, start="2000-06-01", end=None):
        idx = pd.date_range("2000-06-01", pd.Timestamp(end) - pd.Timedelta(days=1), freq="MS", name="date")
        m = idx.month.values
        return pd.Series(40 * (1 + np.cos(2 * np.pi * (m - 1) / 12)) + 5 + self.rng.gamma(2, 8, len(idx)),
                         index=idx, name="precip_mm")

    def _fetch_gpm_monthly_status(self, start="2000-06-01", end=None):
        d = pd.date_range(start, end, freq="MS", inclusive="left", name="date")
        return pd.DataFrame({"status": ["permanent" if x < pd.Timestamp("2025-10-01") else "provisional"
                                        for x in d]}, index=d)

    def _fetch_smap(self, lat, lon, s, e):                           # e EXCLU
        d = pd.date_range(s, e, freq="D", inclusive="left", name="date"); n = len(d)
        return pd.DataFrame(dict(sm_surface=np.full(n, .2), sm_rootzone=np.full(n, .22),
                                 surface_temp=np.full(n, 290.0), sm_rootzone_wetness=np.full(n, .5)), index=d)

    def _modis(self, step, cols, s, e):
        d = pd.date_range(s, e, freq=f"{step}D", inclusive="left", name="date")
        return pd.DataFrame({c: np.linspace(lo, hi, len(d)) for c, (lo, hi) in cols.items()}, index=d)

    def _fetch_modis_reflectance(self, lat, lon, s, e, geometry=None):
        return self._modis(8, dict(red=(.05, .1), nir=(.3, .5), blue=(.03, .05), swir=(.15, .2)), s, e)

    def _fetch_modis_vi(self, lat, lon, s, e, geometry=None):
        return self._modis(16, dict(NDVI=(.2, .7), EVI=(.1, .5)), s, e)

    def _fetch_modis_lst(self, lat, lon, s, e, geometry=None):
        return self._modis(8, dict(LST_Day_1km=(20, 40), LST_Night_1km=(5, 15)), s, e)

    def _fetch_modis_lst_bounds(self, lat, lon, s, e):
        return self._modis(8, dict(lst_min=(18, 22), lst_max=(42, 48)), s, e)

    def _fetch_modis_et(self, lat, lon, s, e, geometry=None):
        return self._modis(8, dict(ET=(5, 15), PET=(20, 35)), s, e)

    def _fetch_soilgrids(self, lat, lon):
        return pd.DataFrame(dict(clay=[30.] * 5, sand=[35.] * 5, silt=[35.] * 5, bdod=[1.35] * 5,
                                 soc=[10., 9, 8, 6, 5], nitrogen=[1., .9, .8, .6, .5], phh2o=[7.8] * 5),
                            index=list(cn.SG_DEPTHS))

    def _fetch_dem_patch(self, lat, lon, **k):
        yy, xx = np.mgrid[0:101, 0:101]
        return 200 + 0.5 * xx + 0.2 * yy + 0.0

    def _fetch_upstream_area_km2(self, lat, lon):
        return 1.5


@pytest.fixture
def sim(monkeypatch, catalogue_csv):
    return Sim(monkeypatch)


def run(start=START, end=END, culture="blé", parcelle=None):
    return ind.get_indicateurs(parcelle or dict(PARCELLE), culture, start, end)


# ---------------------------------------------------------------------------- #
def test_chaine_complete_sans_erreur_et_json_strict(sim):
    r = run()
    assert r["erreurs"] == {}, r["erreurs"]
    assert set(r["indicateurs"]) == {"sol", "power", "gpm", "smap", "modis", "srtm"}
    json.dumps(r, allow_nan=False, ensure_ascii=False)               # NaN/inf interdits
    assert r["periode"] == {"start": START, "end": END, "convention": "start inclus, end exclu"}
    for bloc in r["indicateurs"].values():
        for nom, i in bloc.items():
            assert {"valeur", "unite", "source", "resolution_m", "statut"} <= set(i), nom


def test_nan_et_infini_deviennent_null():
    assert ind._num(float("nan")) is None and ind._num(float("inf")) is None
    assert ind._num(-np.inf) is None and ind._num(np.float64("nan")) is None
    assert ind._num(np.int64(3)) == 3 and type(ind._num(np.int64(3))) is int
    assert ind._num(np.float32(1.23456789)) == 1.2346 and type(ind._num(np.float32(1.5))) is float
    assert ind._num(np.bool_(True)) is True and ind._num("x") == "x" and ind._num(None) is None
    assert json.dumps(ind.I(float("nan"), "-", "gpm"), allow_nan=False)


def test_convention_dates_end_exclu_partout(sim):
    run(start="2025-10-15", end="2026-02-01")
    # POWER : l'API est inclusive -> end - 1 jour
    assert sim.calls["fetch_power"][0][0][2:4] == ("2025-10-15", "2026-01-31")
    # GEE (SMAP, MODIS) : end exclu transmis tel quel
    assert sim.calls["fetch_smap"][0][0][2:4] == ("2025-10-15", "2026-02-01")
    assert sim.calls["fetch_modis_reflectance"][0][0][2:4] == ("2025-10-15", "2026-02-01")
    assert sim.calls["fetch_gpm_daily"][0][0][2:4] == ("2025-10-15", "2026-02-01")


def test_periodes_ecrites_coherentes_et_tronquees(sim):
    r = run()                                         # fin demandée (06-12) > dernières données
    ind_ = r["indicateurs"]
    assert ind_["power"]["GDD"]["periode"] == [START, END]            # POWER disponible jusqu'à aujourd'hui
    assert ind_["gpm"]["CDD"]["periode"] == [START, "2026-04-01"]      # dernier jour GPM 03-31 inclus
    assert ind_["smap"]["RSM_mean"]["periode"] == [START, "2026-04-01"]
    avert = " ".join(r["avertissements"])
    assert "gpm : données disponibles seulement jusqu'au 2026-04-01" in avert
    assert "smap : données disponibles seulement jusqu'au 2026-04-01" in avert
    # la dernière image SMAP (03-31) est bien incluse : 2025-10-15 -> 2026-03-31 = 168 jours
    assert len(sim.calls["fetch_smap"]) == 1
    assert sim.calls["fetch_smap"][0][0][3] == "2026-04-01"


def test_gpm_dernier_jour_incomplet_est_exclu_sans_tuer_les_indices(sim):
    sim.nan_days = ["2026-03-31"]                      # jour en cours : < 48 images
    r = run()
    cdd = r["indicateurs"]["gpm"]["CDD"]
    assert cdd["valeur"] is not None
    assert cdd["periode"] == [START, "2026-03-31"]
    assert any("dernier jour publié (2026-03-31) est incomplet" in w for w in r["avertissements"])


def test_gpm_journee_incomplete_interieure_rend_les_indices_indisponibles(sim):
    sim.nan_days = ["2025-12-01"]
    r = run()
    g = r["indicateurs"]["gpm"]
    for k in ("CDD", "SDII", "R20mm", "Rx1day"):
        assert g[k]["valeur"] is None, k                      # jamais interprété comme jour sec
        assert "1/" in g[k]["note"] and "indisponible" in g[k]["note"]
    assert g["SPI3_last"]["valeur"] is not None              # la partie mensuelle n'est pas affectée
    assert any("journée(s) incomplète(s)" in w and "2025-12-01" in w for w in r["avertissements"])
    json.dumps(r, allow_nan=False)


def test_gpm_valeurs_journalieres_calculees_sur_donnees_simulees(sim):
    g = run()["indicateurs"]["gpm"]
    # Sur la fenêtre simulée [2025-10-15, 2026-04-01) = 168 jours : 1 jour pluvieux sur 5 (6 mm)
    # + un jour à 25 mm à l'indice 10 (indice 10 % 5 == 0 : il remplace un jour de 6 mm).
    n = 168
    pluvieux = np.arange(n) % 5 == 0
    assert g["Rx1day"]["valeur"] == 25.0 and g["R20mm"]["valeur"] == 1
    assert g["CDD"]["valeur"] == 4.0
    assert g["SDII"]["valeur"] == pytest.approx((6.0 * (pluvieux.sum() - 1) + 25.0) / pluvieux.sum(), abs=1e-3)


def test_statuts_de_produit_conserves(sim):
    g = run()["indicateurs"]["gpm"]
    assert g["CDD"]["statut_produit"] == "provisional"          # après le 30/09/2025
    assert "provisional" in g["CDD"]["note"]
    r = run(start="2025-08-01", end="2025-12-01")
    assert r["indicateurs"]["gpm"]["CDD"]["statut_produit"] == "mixed"
    r = run(start="2025-07-01", end="2025-09-01")
    assert r["indicateurs"]["gpm"]["CDD"]["statut_produit"] == "permanent"
    assert r["indicateurs"]["gpm"]["CDD"]["source"] == "GPM IMERG V07"   # plus d'étiquette « Final » trompeuse


def test_statut_inconnu_si_la_requete_de_statut_echoue_mais_indices_conserves(sim):
    sim.fail.add("fetch_gpm_daily_status")
    r = run()
    cdd = r["indicateurs"]["gpm"]["CDD"]
    assert cdd["valeur"] is not None and cdd["statut_produit"] == "unknown"
    assert "gpm.statut_journalier" in r["erreurs"]
    assert any("gpm.statut_journalier" in w for w in r["avertissements"])


def test_echec_gpm_mensuel_conserve_gpm_journalier_et_autres_sources(sim):
    sim.fail.add("fetch_gpm_monthly")
    r = run()
    assert "gpm.mensuel" in r["erreurs"]
    g = r["indicateurs"]["gpm"]
    assert g["CDD"]["valeur"] is not None and "SPI3_last" not in g
    assert {"power", "smap", "modis", "srtm", "sol"} <= set(r["indicateurs"])


def test_echec_gpm_journalier_conserve_spi_pci(sim):
    sim.fail.add("fetch_gpm_daily")
    r = run()
    assert "gpm.journalier" in r["erreurs"] and "CDD" not in r["indicateurs"]["gpm"]
    assert r["indicateurs"]["gpm"]["SPI3_last"]["valeur"] is not None
    # sans pluie GPM, le dry-down SMAP est signalé comme non calculé
    assert any("Dry-down non calculé" in w for w in r["avertissements"])


def test_echec_total_gpm_nempeche_pas_les_autres_blocs(sim):
    sim.fail.update({"fetch_gpm_daily", "fetch_gpm_monthly"})
    r = run()
    assert "gpm" in r["erreurs"] and "gpm" not in r["indicateurs"]
    assert {"power", "smap", "modis", "srtm", "sol"} <= set(r["indicateurs"])
    json.dumps(r, allow_nan=False)


@pytest.mark.parametrize("source, bloc", [
    ("fetch_power", "power"), ("fetch_smap", "smap"), ("fetch_soilgrids", "sol"),
    ("fetch_dem_patch", "srtm")])
def test_isolation_des_erreurs_entre_sources(sim, source, bloc):
    sim.fail.add(source)
    r = run()
    assert bloc in r["erreurs"] and bloc not in r["indicateurs"]
    restants = {"sol", "power", "gpm", "smap", "modis", "srtm"} - {bloc}
    if bloc == "sol":
        restants -= {"smap"}                           # SMAP dépend des propriétés du sol (documenté)
    assert restants <= set(r["indicateurs"]), r["erreurs"]
    assert any(f"Bloc « {bloc} » indisponible" in w for w in r["avertissements"])


def test_modis_echec_partiel(sim):
    sim.fail.add("fetch_modis_lst")
    r = run()
    assert "modis.tvdi" in r["erreurs"]
    assert "NDVI_mean" in r["indicateurs"]["modis"] and "TVDI_mean" not in r["indicateurs"]["modis"]


def test_spi_et_pci_ne_depassent_pas_la_fin_de_periode(sim):
    r = run(start="2025-01-01", end="2025-12-15")
    g = r["indicateurs"]["gpm"]
    assert g["SPI3_last"]["periode"] == ["2025-11"]            # novembre = dernier mois ENTIER avant end
    assert g["SPI12_last"]["periode"] == ["2025-11"]
    assert "PCI_2024" in g and "PCI_2025" not in g
    r2 = run()                                                  # fin > dernier mois publié (02-2026)
    assert r2["indicateurs"]["gpm"]["SPI3_last"]["periode"] == ["2026-02"]
    assert "PCI_2025" in r2["indicateurs"]["gpm"]


def test_gpm_mensuel_appele_avec_une_fin_independante_de_la_periode(sim):
    run(); run(start="2025-01-01", end="2025-12-15")
    fins = {k["end"] for _, k in sim.calls["fetch_gpm_monthly"]}
    assert fins == {"2026-03-01"}                              # même clé de cache dans les deux cas


def test_spi_statut_produit_selon_les_mois_du_cumul(sim):
    g = run()["indicateurs"]["gpm"]
    assert g["SPI3_last"]["statut_produit"] == "provisional"   # déc., janv., fév. : après 09/2025
    r = run(start="2025-01-01", end="2025-10-01")              # dernier mois = sept. 2025 (permanent)
    assert r["indicateurs"]["gpm"]["SPI3_last"]["statut_produit"] == "permanent"


def test_power_valeurs_manquantes_signalees(sim, monkeypatch):
    base = sim._fetch_power
    def avec_trou(lat, lon, s, e, parameters=None):
        df = base(lat, lon, s, e, parameters)
        if parameters is None:
            df.loc[df.index[3], "PRECTOTCORR"] = np.nan
        return df
    monkeypatch.setattr(cn, "fetch_power", avec_trou)
    r = run()
    assert any("1 jour(s) avec valeur manquante" in w for w in r["avertissements"])


def test_periodes_invalides(sim):
    with pytest.raises(ValueError, match="start"):
        run(start="2026-01-01", end="2026-01-01")
    with pytest.raises(ValueError, match="start"):
        run(start="2026-02-01", end="2026-01-01")


def test_avertissement_resolution_et_sol(sim):
    r = run()
    w = " ".join(r["avertissements"])
    assert "NASA POWER" in w and "plus grossière" in w and "SoilGrids" in w


def test_culture_inconnue(sim):
    with pytest.raises(KeyError):
        run(culture="culture-inexistante")


def test_sol_mesure_complet_sans_soilgrids(sim):
    sim.fail.add("fetch_soilgrids")
    p = dict(PARCELLE, sol_mesure=dict(sand=20, clay=45, soc=8, nitrogen=.8, phh2o=7.9, bdod=1.3))
    r = run(parcelle=p)
    assert r["statut_sol"] == "mesurée" and "sol" in r["indicateurs"] and "sol" not in r["erreurs"]
