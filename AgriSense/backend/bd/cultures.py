"""
cultures.py : catalogue des cultures lu depuis MySQL (base `nasa_challenge`, table `culture`).

    get_culture("blé")        -> dict de paramètres utilisé par indicateurs_service
    lister_cultures()         -> liste des cultures disponibles en base

Une culture se retrouve par code EcoPort ("2114"), nom scientifique ("Triticum aestivum") ou
n'importe quel nom commun de la colonne `comname` ("blé", "wheat", "orge", "tournesol"...),
sans tenir compte des accents ni de la casse.

Colonnes de la table -> paramètres du modèle :
    t_base -> tbase | t_upper -> t_upper (plafond GDD) | gdd_maturite -> gdd_requis
    kc_mid -> kc (kc_ini, kc_end aussi exposés) | zr_mm | ph_min, ph_max, ph_opt | duree_cycle

Colonnes OPTIONNELLES (à ajouter à la table si tu veux les fixer toi-même) :
    semis_mois, semis_jour, recolte_mois, recolte_jour, seuil_praticable
Sinon : semis dérivé de `saison` (hiver/automne -> 15 oct, printemps/été -> 15 mars), récolte =
semis + duree_cycle, seuil_praticable = 0.8. Ces valeurs par défaut sont signalées dans le résultat
(`dates_derivees`, `seuil_praticable_defaut`).
"""
from __future__ import annotations

import datetime as dt
import difflib
import unicodedata
from functools import lru_cache

import pandas as pd
import pymysql

from .config import DB_CONFIG, DB_NAME, TABLE_CULTURE

# Valeurs par défaut quand la table ne les contient pas (voir docstring)
SEMIS_PAR_SAISON = {"hiver": (10, 15), "automne": (10, 15), "printemps": (3, 15), "été": (3, 15)}
SEUIL_PRATICABLE_DEFAUT = 0.8
GDD_PLAFOND_DEFAUT = 30.0          # plafond du PDF si t_upper est vide
REQUIS = ("t_base", "gdd_maturite", "kc_mid", "zr_mm", "ph_min", "ph_max")


# --------------------------------------------------------------------------- #
# Lecture de la table
# --------------------------------------------------------------------------- #
def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return " ".join(s.casefold().split())


def _lire_table() -> pd.DataFrame:
    """SELECT * sur la table des cultures (point d'injection pour les tests)."""
    conn = pymysql.connect(**DB_CONFIG, database=DB_NAME, charset="utf8mb4",
                           cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM `{TABLE_CULTURE}`")
            rows = cur.fetchall()
    finally:
        conn.close()
    return pd.DataFrame(rows)


def lire_csv(chemin: str) -> pd.DataFrame:
    """Lit le CSV avec la même normalisation de colonnes que MySQLIngestor (tests hors base)."""
    from .mysql_ingestor import MySQLIngestor
    df = pd.read_csv(chemin, sep=None, engine="python")
    df.columns = [MySQLIngestor._clean_name(c) for c in df.columns]
    return df


@lru_cache(maxsize=1)
def _catalogue() -> pd.DataFrame:
    df = _lire_table()
    if df.empty:
        raise RuntimeError(f"Table `{DB_NAME}.{TABLE_CULTURE}` vide : lance bd/connection.py.")
    df.columns = [c.lower() for c in df.columns]
    # ingestions répétées -> doublons : on garde la plus récente par code EcoPort
    if "_ingested_at" in df.columns:
        df = df.sort_values("_ingested_at")
    return df.drop_duplicates("ecoportcode", keep="last").reset_index(drop=True)


def recharger() -> None:
    """Vide le cache (à appeler après une nouvelle ingestion)."""
    _catalogue.cache_clear()


# --------------------------------------------------------------------------- #
# Recherche
# --------------------------------------------------------------------------- #
def _noms(row) -> list[str]:
    return [n.strip() for n in str(row.get("comname") or "").split(",") if n.strip()]


def lister_cultures() -> list[dict]:
    out = []
    for _, r in _catalogue().iterrows():
        out.append({"code": int(r["ecoportcode"]), "nom_scientifique": r["scientificname"],
                    "noms": _noms(r), "famille": r.get("famille"), "saison": r.get("saison")})
    return out


def _trouver(ident) -> pd.Series:
    df, cle = _catalogue(), _norm(ident)
    hits = [i for i, r in df.iterrows()
            if cle in {_norm(r["ecoportcode"]), _norm(r["scientificname"]),
                       *(_norm(n) for n in _noms(r))}]
    if len(hits) == 1:
        return df.loc[hits[0]]
    if len(hits) > 1:
        cand = [df.loc[i, "scientificname"] for i in hits]
        raise ValueError(f"« {ident} » est ambigu : {cand}. Précise le code EcoPort ou le nom scientifique.")
    tous = {_norm(n): n for _, r in df.iterrows() for n in _noms(r)}
    proches = [tous[k] for k in difflib.get_close_matches(cle, tous, n=5, cutoff=0.6)]
    raise KeyError(f"Culture « {ident} » absente de {DB_NAME}.{TABLE_CULTURE}. "
                   f"Cultures disponibles : {[c['nom_scientifique'] for c in lister_cultures()]}"
                   + (f". Proches : {proches}" if proches else ""))


# --------------------------------------------------------------------------- #
# Construction du dict de paramètres
# --------------------------------------------------------------------------- #
def _v(row, col, cast=float):
    """Valeur native Python, ou None si NULL / colonne absente."""
    if col not in row.index or pd.isna(row[col]):
        return None
    return cast(row[col])


def _semis_recolte(row, duree):
    sm, sj = _v(row, "semis_mois", int), _v(row, "semis_jour", int)
    rm, rj = _v(row, "recolte_mois", int), _v(row, "recolte_jour", int)
    if None not in (sm, sj, rm, rj):
        return (sm, sj), (rm, rj), False
    saison = _norm(row.get("saison") or "")
    debut = next((d for k, d in SEMIS_PAR_SAISON.items() if _norm(k) in saison), None)
    if debut is None or duree is None:
        raise ValueError(f"Culture {row['scientificname']} : impossible de dériver la fenêtre de semis "
                         "(colonnes `saison` / `duree_cycle` inexploitables). Ajoute semis_mois, semis_jour, "
                         "recolte_mois, recolte_jour à la table.")
    fin = dt.date(2001, *debut) + dt.timedelta(days=int(round(duree)))   # 2001 : non bissextile
    return debut, (fin.month, fin.day), True


def get_culture(ident) -> dict:
    """Paramètres de la culture `ident` (code, nom scientifique ou nom commun) lus en base."""
    r = _trouver(ident)
    manquants = [c for c in REQUIS if _v(r, c) is None]
    if manquants:
        raise ValueError(f"Culture {r['scientificname']} : champs vides en base : {manquants}")
    duree = _v(r, "duree_cycle")
    semis, recolte, derivees = _semis_recolte(r, duree)
    seuil = _v(r, "seuil_praticable")
    return {
        "nom": str(ident),
        "code": int(r["ecoportcode"]),
        "nom_scientifique": r["scientificname"],
        "famille": _v(r, "famille", str),
        "n_fixer": _v(r, "n_fixer", bool),
        "saison": _v(r, "saison", str),
        "tbase": _v(r, "t_base"),
        "t_upper": _v(r, "t_upper") or GDD_PLAFOND_DEFAUT,
        "gdd_requis": _v(r, "gdd_maturite"),
        "kc": _v(r, "kc_mid"),
        "kc_ini": _v(r, "kc_ini"),
        "kc_end": _v(r, "kc_end"),
        "zr_mm": _v(r, "zr_mm"),
        "ph_min": _v(r, "ph_min"),
        "ph_max": _v(r, "ph_max"),
        "ph_opt": _v(r, "ph_opt"),
        "duree_cycle": duree,
        "seuil_praticable": SEUIL_PRATICABLE_DEFAUT if seuil is None else seuil,
        "seuil_praticable_defaut": seuil is None,
        "semis": semis,
        "recolte": recolte,
        "dates_derivees": derivees,
        "source": f"MySQL {DB_NAME}.{TABLE_CULTURE} (EcoPort {int(r['ecoportcode'])}, FAO-56/EcoCrop)",
    }
