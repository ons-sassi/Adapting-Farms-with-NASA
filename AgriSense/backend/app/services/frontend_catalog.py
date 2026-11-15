"""Catalogue des cultures servi au frontend (fichiers CSV de data/catalog).

Sources : catalogue_cultures_v6.csv (EcoCrop + FAO-56 + AquaCrop), calendrier FAO
Tunisie et noms d'affichage français. Aucune base MySQL n'est nécessaire : le
catalogue est lu une fois puis gardé en mémoire.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd

CATALOG_DIR = Path(__file__).resolve().parents[2] / "data" / "catalog"

# Zones du formulaire parcelle (frontend) -> libellés du calendrier FAO Tunisie.
ZONE_TO_FAO = {
    "Kroumirie - Mogods": "Kroumirie - Mogods",
    "Sub-humide": "Sub-humid",
    "Semi-aride à hiver frais": "Semiarid fresh winter",
    "Nord-Est et Cap Bon": "North East and Cap Bon (semi arid with mild winters)",
    "Dorsale et Tell (Kairouan)": "Dorsal and Tell (Kairouan)",
    "Basse steppe": "Lower Steppe (arid with mild winters)",
    "Sidi Bouzid": "Sidi Bouzid",
}

FAMILY_FR = {
    "gramineae": "Poacées", "poaceae": "Poacées",
    "leguminosae": "Fabacées", "fabaceae": "Fabacées",
    "solanaceae": "Solanacées", "compositae": "Astéracées", "asteraceae": "Astéracées",
    "cruciferae": "Brassicacées", "cucurbitaceae": "Cucurbitacées",
    "alliaceae": "Alliacées", "umbelliferae": "Apiacées",
    "chenopodiaceae": "Amaranthacées", "malvaceae": "Malvacées",
    "pedaliaceae": "Pédaliacées", "asparagaceae": "Asparagacées", "oleaceae": "Oléacées",
}
OILSEEDS = {"Helianthus annuus", "Carthamus tinctorius", "Sesamum indicum", "Brassica napus",
            "Arachis hypogaea", "Glycine max"}
FORAGE = {"Medicago sativa", "Zea mays ssp. saccharata", "Avena sativa"}
INDUSTRIAL = {"Beta vulgaris", "Gossypium hirsutum"}

# Fenêtres de semis par défaut quand le calendrier FAO ne couvre pas la culture.
DEFAULT_WINDOWS = {"hiver": ("10-15", "11-30"), "printemps": ("03-01", "04-30")}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")


def _num(value):
    return None if value is None or pd.isna(value) else float(value)


def _water_class(raw) -> str:
    raw = str(raw or "").casefold()
    if raw.startswith("faible"):
        return "Faible"
    if raw.startswith("moyen"):
        return "Moyen"
    if raw.startswith("élevé") or raw.startswith("eleve"):
        return "Élevé"
    return "Inconnu"


def _crop_type(sci: str, family: str) -> str:
    f = family.casefold()
    if sci in FORAGE:
        return "Fourrage"
    if sci in OILSEEDS:
        return "Oléagineux"
    if sci in INDUSTRIAL:
        return "Culture industrielle"
    if f in ("gramineae", "poaceae"):
        return "Céréale"
    if f in ("leguminosae", "fabaceae"):
        return "Légumineuse"
    if sci == "Olea europaea":
        return "Arboriculture"
    return "Maraîchage"


@lru_cache(maxsize=1)
def _calendar() -> pd.DataFrame:
    cal = pd.read_csv(CATALOG_DIR / "calendrier_FAO_Tunisie.csv")
    return cal.dropna(subset=["ScientificName"])


def _windows(sci: str) -> pd.DataFrame:
    cal = _calendar()
    rows = cal[cal.ScientificName == sci]
    # Une ligne par zone : on garde la conduite "production grain" si elle existe.
    if rows.empty:
        return rows
    rows = rows.assign(_grain=rows.usage_ou_conduite.fillna("").str.contains("grain"))
    return rows.sort_values("_grain", ascending=False).drop_duplicates("zone_agroecologique")


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, dict]:
    names = json.loads((CATALOG_DIR / "noms_affichage_fr.json").read_text(encoding="utf-8"))
    df = pd.read_csv(CATALOG_DIR / "catalogue_cultures_v6.csv", low_memory=False)
    df = df[df.ScientificName.isin(names)].drop_duplicates("ScientificName")
    crops: dict[str, dict] = {}
    for _, r in df.iterrows():
        sci = r.ScientificName
        family = str(r.famille or "")
        win = _windows(sci)
        cycle = _num(r.duree_cycle)
        if cycle is None and not win.empty:
            # "90 - 100" -> 95 ; valeurs vides ignorées
            periods = [sum(map(float, str(v).split("-"))) / len(str(v).split("-"))
                       for v in win.growing_period_days.dropna()]
            cycle = sum(periods) / len(periods) if periods else None
        if cycle is None and _num(r.GMIN) and _num(r.GMAX):
            cycle = (float(r.GMIN) + float(r.GMAX)) / 2   # plage EcoCrop
        saison = str(r.saison or "").casefold()
        season = "Hiver" if "hiver" in saison else "Printemps / été" if "printemps" in saison else None
        if season is None and not win.empty:
            month = int(win.semis_debut_mois.iloc[0])
            season = "Hiver" if month >= 8 or month <= 1 else "Printemps / été"
        perennial = "perennial" in str(r.annuelle_perenne or "") and "annual" not in str(r.annuelle_perenne or "")
        ph_min, ph_max = _num(r.ph_min), _num(r.ph_max)
        name = names[sci]
        crop = {
            "id": slugify(name),
            "name": name,
            "scientificName": sci,
            "code": int(r.EcoPortCode),
            "family": FAMILY_FR.get(family.casefold(), family),
            "familyLatin": family,
            "type": _crop_type(sci, family),
            "season": season or "—",
            "cycle": f"{int(cycle)} j" if cycle else "—",
            "cycleDays": int(cycle) if cycle else None,
            "water": _water_class(r.besoin_eau),
            "soil": f"pH {ph_min:g}–{ph_max:g}" if ph_min and ph_max else "—",
            "nFixer": bool(r.n_fixer) if not pd.isna(r.n_fixer) else None,
            "rootDepthM": (_num(r.zr_mm) or 0) / 1000 or None,
            "kcIni": _num(r.kc_ini),
            "kcMid": _num(r.kc_mid),
            "tBase": _num(r.t_base),
            "gddMaturity": _num(r.gdd_maturite),
            "phMin": ph_min, "phOpt": _num(r.ph_opt), "phMax": ph_max,
            "tuber": bool(r.tubercule) if not pd.isna(r.tubercule) else False,
            "coverCrop": bool(r.culture_couverture) if not pd.isna(r.culture_couverture) else False,
            "perennial": perennial,
            "zones": sorted(win.zone_agroecologique.tolist()) if not win.empty else [],
        }
        # Éligible à une rotation annuelle : cycle connu, non pérenne, famille connue.
        crop["eligible"] = bool(crop["cycleDays"] and crop["cycleDays"] <= 300 and not perennial and family)
        crops[crop["id"]] = crop
    return dict(sorted(crops.items(), key=lambda kv: kv[1]["name"]))


def list_crops(eligible_only: bool = False) -> list[dict]:
    crops = load_catalog().values()
    return [c for c in crops if c["eligible"] or not eligible_only]


def get_crop(crop_id: str) -> dict | None:
    return load_catalog().get(crop_id)


def sowing_window(crop: dict, zone_fr: str | None) -> tuple[str, str, str]:
    """(début MM-DD, fin MM-DD, provenance) pour la zone de la parcelle."""
    win = _windows(crop["scientificName"])
    fao_zone = ZONE_TO_FAO.get(zone_fr or "")
    picked, origin = None, None
    if not win.empty:
        match = win[win.zone_agroecologique == fao_zone] if fao_zone else win.iloc[0:0]
        if not match.empty:
            picked, origin = match.iloc[0], "calendrier FAO (zone de la parcelle)"
        else:
            picked, origin = win.iloc[0], f"calendrier FAO ({win.iloc[0].zone_agroecologique})"
    if picked is not None:
        start = f"{int(picked.semis_debut_mois):02d}-{int(picked.semis_debut_jour):02d}"
        end = f"{int(picked.semis_fin_mois):02d}-{int(picked.semis_fin_jour):02d}"
        return start, end, origin
    key = "hiver" if crop["season"].startswith("Hiver") else "printemps"
    return (*DEFAULT_WINDOWS[key], "fenêtre par défaut selon la saison")
