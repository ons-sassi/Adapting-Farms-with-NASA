"""Tests unitaires de common/indices.py (fonctions pures, aucune donnée réseau)."""
import numpy as np
import pandas as pd
import pytest
from scipy.stats import gamma, norm

from common import indices as ix


def daily(values, start="2025-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="D"), dtype=float)


# ------------------------------- CDD ---------------------------------------- #
def test_cdd_valeur_connue():
    # secs (<1 mm) : 0,0 | 5 | 0,0,0 | 2 | 0  -> plus longue séquence = 3
    assert ix.cdd(daily([0, 0, 5, 0, 0, 0, 2, 0])) == 3


def test_cdd_seuil_strict_1mm():
    # 1.0 mm est un jour PLUVIEUX (sec = < 1 mm) : il coupe la séquence
    assert ix.cdd(daily([0, 0, 1.0, 0])) == 2


def test_cdd_toute_la_serie_seche():
    assert ix.cdd(daily([0.0] * 30)) == 30


def test_cdd_nan_nest_pas_un_jour_sec():
    assert np.isnan(ix.cdd(daily([0, 0, np.nan, 0, 0])))


def test_cdd_serie_vide_ou_trou_de_dates():
    assert np.isnan(ix.cdd(daily([])))
    s = daily([0, 0, 0, 0]).drop(pd.Timestamp("2025-01-03"))     # un jour absent de l'index
    assert np.isnan(ix.cdd(s))


def test_cdd_valeurs_invalides():
    assert np.isnan(ix.cdd(daily([0, -1.0, 0])))
    assert np.isnan(ix.cdd(daily([0, np.inf, 0])))


# ------------------------------- SDII --------------------------------------- #
def test_sdii_valeur_connue():
    # jours >= 1 mm : 2, 4, 6 -> moyenne 4 ; 0.5 et 0 ne comptent pas
    assert ix.sdii(daily([0, 2, 4, 0.5, 6])) == pytest.approx(4.0)


def test_sdii_sans_jour_pluvieux_est_indefini():
    assert np.isnan(ix.sdii(daily([0, 0.2, 0.9])))


def test_sdii_nan():
    assert np.isnan(ix.sdii(daily([1, np.nan, 3])))


# ------------------------------- R20mm / Rx1day ----------------------------- #
def test_r20mm_seuil_inclusif():
    assert ix.r20mm(daily([19.99, 20.0, 35, 0])) == 2


def test_r20mm_et_rx1day_nan():
    s = daily([1, np.nan, 30])
    assert np.isnan(ix.r20mm(s)) and np.isnan(ix.rx1day(s))


def test_rx1day():
    assert ix.rx1day(daily([1, 42.5, 3])) == 42.5
    assert np.isnan(ix.rx1day(daily([])))


# ------------------------------- PCI ---------------------------------------- #
def monthly_year(values, year=2024):
    return pd.Series(values, index=pd.date_range(f"{year}-01-01", periods=len(values), freq="MS"),
                     dtype=float)


def test_pci_repartition_uniforme_est_100_sur_12():
    assert ix.pci(monthly_year([50.0] * 12)) == pytest.approx(100 / 12)


def test_pci_un_seul_mois_pluvieux_vaut_100():
    assert ix.pci(monthly_year([0] * 11 + [80])) == pytest.approx(100.0)


def test_pci_formule_oliver():
    p = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120], float)
    assert ix.pci(monthly_year(p)) == pytest.approx(100 * (p ** 2).sum() / p.sum() ** 2)


@pytest.mark.parametrize("vals", [
    [10.0] * 11,                         # année incomplète
    [10.0] * 13,                         # trop de mois
    [10.0] * 11 + [np.nan],              # mois manquant
    [10.0] * 11 + [-1.0],                # précipitation négative
    [10.0] * 11 + [np.inf],              # valeur infinie
    [0.0] * 12,                          # cumul annuel nul (division par zéro)
])
def test_pci_rejets(vals):
    assert np.isnan(ix.pci(pd.Series(vals, dtype=float)))


def test_pci_rejette_deux_annees_melangees():
    idx = pd.date_range("2023-07-01", periods=12, freq="MS")   # juillet 2023 -> juin 2024
    assert np.isnan(ix.pci(pd.Series(np.arange(1, 13, dtype=float), index=idx)))


# ------------------------------- SPI ---------------------------------------- #
def serie_mensuelle(n_years=40, seed=1, start="1985-01-01", a=2.0, scale=20.0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=12 * n_years, freq="MS")
    return pd.Series(rng.gamma(a, scale, len(idx)), index=idx)


def test_spi_normalise_et_fini():
    p = serie_mensuelle(60)
    for k in (1, 3, 12):
        s = ix.spi(p, k).dropna()
        assert np.isfinite(s).all()
        assert abs(s.mean()) < 0.1 and abs(s.std() - 1) < 0.1


def test_spi_k_premiers_mois_nan():
    p = serie_mensuelle(30)
    s = ix.spi(p, 3)
    assert s.iloc[:2].isna().all() and s.iloc[2:].notna().all()


def test_spi_reference_independante_sur_gamma_connue():
    """SPI1 estimé vs z théorique norm.ppf(F_vraie(x)) sur une loi Gamma connue."""
    a, scale = 2.5, 18.0
    p = serie_mensuelle(300, seed=7, a=a, scale=scale)
    est = ix.spi(p, 1)
    vrai = pd.Series(norm.ppf(gamma.cdf(p, a, scale=scale)), index=p.index)
    assert np.corrcoef(est.dropna(), vrai[est.notna()])[0, 1] > 0.99
    assert (est.dropna() - vrai[est.notna()]).abs().max() < 0.25


def test_spi_monotone_par_mois_calendaire():
    p = serie_mensuelle(40)
    s = ix.spi(p, 1)
    jan = pd.DataFrame({"p": p, "s": s})[p.index.month == 1].dropna().sort_values("p")
    assert jan["s"].is_monotonic_increasing


def test_spi_probabilite_de_zero_sans_infini():
    p = serie_mensuelle(40)
    p[p.index.month == 7] = np.where(np.arange(40) % 3 == 0, 0.0, p[p.index.month == 7])  # ~1/3 de zéros en juillet
    s = ix.spi(p, 1)
    jul = s[s.index.month == 7].dropna()
    assert len(jul) == 40 and np.isfinite(jul).all()
    zeros = jul[p[p.index.month == 7] == 0]
    assert zeros.nunique() == 1 and zeros.iloc[0] < 0         # tous les zéros -> même SPI négatif


def test_spi_serie_constante_est_nan():
    p = pd.Series(25.0, index=pd.date_range("1990-01-01", periods=12 * 30, freq="MS"))
    assert ix.spi(p, 3).isna().all()


def test_spi_mois_toujours_a_zero_est_nan():
    p = serie_mensuelle(30)
    p[p.index.month == 8] = 0.0
    s = ix.spi(p, 1)
    assert s[s.index.month == 8].isna().all()
    assert s[s.index.month == 9].notna().all()


def test_spi_historique_insuffisant():
    assert ix.spi(serie_mensuelle(15), 3).isna().all()          # < 20 ans


def test_spi_mois_absent_de_lindex_equivaut_a_un_nan():
    """Un mois supprimé (au lieu d'être NaN) ne doit PAS décaler les cumuls glissants."""
    p = serie_mensuelle(40)
    manque = p.drop(p.index[200])
    avec_nan = p.copy()
    avec_nan.iloc[200] = np.nan
    a, b = ix.spi(manque, 3), ix.spi(avec_nan, 3)
    pd.testing.assert_series_equal(a, b)
    assert a.iloc[200:203].isna().all()          # les cumuls qui contiennent le mois manquant


def test_spi_nan_propage_dans_le_cumul():
    p = serie_mensuelle(30)
    p.iloc[100] = np.nan
    s = ix.spi(p, 3)
    assert s.iloc[100:103].isna().all()


def test_spi_entrees_invalides():
    p = serie_mensuelle(30)
    q = p.copy(); q.iloc[5] = -3.0
    with pytest.raises(ValueError):
        ix.spi(q, 3)
    with pytest.raises(ValueError):
        ix.spi(p, 0)
    with pytest.raises(TypeError):
        ix.spi(pd.Series([1.0, 2.0]), 3)
    r = p.copy(); r.iloc[10] = np.inf
    assert np.isfinite(ix.spi(r, 3).dropna()).all()             # inf traité comme manquant


# ------------------------- NaN non masqués ---------------------------------- #
def test_score_ph_nan_reste_nan():
    assert np.isnan(ix.score_ph(float("nan"), 6.0, 7.5))
    assert ix.score_ph(7.0, 6.0, 7.5) == 1.0
    # hors plage : décroissance linéaire depuis le pH OPTIMAL (milieu de plage par défaut = 6.75)
    assert ix.score_ph(7.8, 6.0, 7.5) == pytest.approx(1 - abs(7.8 - 6.75) / 1.5)
    assert ix.score_ph(9.0, 6.0, 7.5) == 0.0


def test_rsm_class():
    assert ix.rsm_class(float("nan")) is None
    assert ix.rsm_class(-0.1) == "stress hydrique critique"
    assert ix.rsm_class(0.6) == "confort hydrique optimal"
    assert ix.rsm_class(1.2).startswith("saturation")
    assert ix.rsm_class(0.2) == "intermédiaire"


# ------------------------- POWER / sol (formules) --------------------------- #
def test_gdd_plafond_et_plancher():
    # Tmax plafonnée à 30, Tmin plancher à Tbase=10 : (30+10)/2-10 = 10 ; froid -> 0
    assert ix.gdd(np.array([40.0, 5.0]), np.array([2.0, 0.0]), tbase=10) == pytest.approx(10.0)


def test_et0_ete_semi_aride_plausible():
    idx = pd.date_range("2025-07-01", periods=5, freq="D")
    df = pd.DataFrame({"T2M_MAX": 36.0, "T2M_MIN": 22.0, "WS2M": 3.0, "RH2M": 40.0,
                       "ALLSKY_SFC_SW_DWN": 27.0, "T2MDEW": 12.0}, index=idx)
    et0 = ix.et0_fao56(df, lat=35.68, elevation=80)
    assert ((et0 > 5) & (et0 < 10)).all()
    assert (ix.et0_fao56(df.assign(RH2M=80.0), 35.68, 80) < et0).all()   # air plus humide -> ET0 plus faible


def test_saxton_rawls_limon_et_conversions_sol():
    fc, pwp = ix.saxton_rawls(40, 20, 2.5)
    assert 0.2 < fc < 0.35 and 0.07 < pwp < 0.16 and fc > pwp
    assert ix.som_pct(10) == pytest.approx(1.724)          # 10 g/kg de C -> 1.724 % de MO
    assert ix.theta_sat(1.325) == pytest.approx(0.5)


def test_frost_and_heat_days():
    assert ix.frost_days(pd.Series([-1.0, 0.0, 3.0])) == 1
    assert ix.heat_stress_days(pd.Series([35.0, 35.1, 40.0]), 35) == 2
