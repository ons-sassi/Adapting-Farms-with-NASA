"""Tests sur les EXPORTS RÉELS fournis avec le projet (CSV produits par de vrais appels GEE
sur le point 35.6815 N / 10.102 E). Ce ne sont pas des appels GEE : ils vérifient la cohérence
des données réelles déjà extraites et la conversion journalier <-> mensuel."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.real_exports


@pytest.fixture(scope="module")
def controle():
    return pd.read_csv(ROOT / "gpm_daily_controle_complet.csv", parse_dates=["date"])


@pytest.fixture(scope="module")
def comparaison():
    return pd.read_csv(ROOT / "gpm_daily_monthly_comparison.csv", index_col=0, parse_dates=True)


def test_controle_journalier_coherent(controle):
    c = controle
    assert not c["date"].duplicated().any()
    assert c["date"].is_monotonic_increasing
    assert len(c) == len(pd.date_range(c["date"].min(), c["date"].max(), freq="D"))   # aucun jour absent
    assert (c["expected_count"] == 48).all()                                           # 48 demi-heures/jour
    assert (c["image_count"] <= 48).all()
    assert (c["missing_images"] == 48 - c["image_count"]).all()
    assert ((c["image_count"] == 48) == (c["status"] == "COMPLET")).all()


def test_bilan_annuel_et_anomalies_coherents_avec_le_controle(controle):
    b = pd.read_csv(ROOT / "gpm_daily_bilan_annuel.csv").set_index("year")
    g = controle.groupby("year")
    assert (g.size() == b["jours_controles"]).all()
    assert (g["status"].apply(lambda s: (s == "COMPLET").sum()) == b["jours_complets"]).all()
    assert (g["missing_images"].sum() == b["images_manquantes"]).all()
    a = pd.read_csv(ROOT / "gpm_daily_anomalies.csv", parse_dates=["date"])
    attendu = controle[controle["status"] != "COMPLET"]
    assert a["date"].tolist() == attendu["date"].tolist()


def test_journees_incompletes_reelles_sont_rares_mais_existent(controle):
    inc = controle[controle["status"] != "COMPLET"]
    assert 0 < len(inc) / len(controle) < 0.001          # 3 jours sur 9662
    # le dernier jour publié est un jour EN COURS (peu d'images) : cas traité par _gpm
    assert controle.iloc[-1]["image_count"] < 48


def test_reconstruction_journaliere_vs_mensuel_officiel(comparaison):
    m = comparaison.dropna(subset=["gpm_monthly", "precip_mm"])
    assert len(m) >= 8
    fortes = m[m["gpm_monthly"] >= 5]
    assert (fortes["difference_percent"].abs() < 2.5).all(), fortes[["precip_mm", "gpm_monthly"]]
    faibles = m[m["gpm_monthly"] < 5]
    assert (faibles["difference_mm"].abs() < 2.5).all()   # mois quasi secs : écart absolu faible


def test_mois_incomplets_restent_nan_dans_la_reconstruction(comparaison, controle):
    assert (comparaison["expected_days"] == comparaison.index.days_in_month).all()
    complets_par_mois = (controle[controle["status"] == "COMPLET"]
                         .groupby(controle["date"].dt.to_period("M").dt.to_timestamp())
                         .size())
    for mois, ligne in comparaison.iterrows():
        assert ligne["count"] == complets_par_mois.get(mois, 0), mois
        if ligne["count"] < ligne["expected_days"]:
            assert np.isnan(ligne["precip_mm"]), mois          # mois non complet : jamais de cumul partiel


def test_mensuel_v07_absent_apres_septembre_2025(comparaison):
    """Constat sur données réelles : IMERG_MONTHLY_V07 est vide à partir d'octobre 2025
    (cohérent avec la note du catalogue : plus de produit `permanent` après le 2025-09-30).
    Conséquence : SPI/PCI ne peuvent pas couvrir les saisons récentes."""
    assert comparaison.loc[:"2025-09-01", "gpm_monthly"].notna().all()
    assert comparaison.loc["2025-10-01":, "gpm_monthly"].isna().all()


def test_ecart_connu_juin_2025_cumul_journalier_nul_mais_mensuel_positif(comparaison):
    """Écart réel non expliqué à ce stade : 0.00 mm (somme des 48 demi-heures) contre 2.16 mm
    (mensuel). À investiguer ; ce test fige le constat pour qu'un changement soit visible."""
    j = comparaison.loc["2025-06-01"]
    assert j["precip_mm"] == pytest.approx(0.0, abs=1e-9) and j["gpm_monthly"] == pytest.approx(2.16, abs=0.01)
