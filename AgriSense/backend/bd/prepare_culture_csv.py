"""Prépare le CSV + manifeste du catalogue cultures pour bd/connection.py.

Source : data/catalog/catalogue_cultures_v6.csv, limité aux cultures de
data/catalog/noms_affichage_fr.json (cultures utiles en Tunisie). Les noms français
sont ajoutés en tête de `comname` pour que get_culture("blé dur") fonctionne.

    python bd/prepare_culture_csv.py
    python bd/connection.py --manifest bd/data/manifest_catalogue_v6.json --csv bd/data/cultures_catalogue_v6.csv
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "catalog"
OUT = Path(__file__).resolve().parent / "data"
COLUMNS = ["ecoportcode", "scientificname", "comname", "famille", "saison", "n_fixer",
           "t_base", "t_upper", "gdd_maturite", "kc_mid", "kc_ini", "kc_end",
           "zr_mm", "ph_min", "ph_max", "ph_opt", "duree_cycle"]
UNITS = {"t_base": "degC", "t_upper": "degC", "gdd_maturite": "degC_day", "kc_mid": "1",
         "kc_ini": "1", "kc_end": "1", "zr_mm": "mm", "ph_min": "pH", "ph_max": "pH",
         "ph_opt": "pH", "duree_cycle": "day"}

if __name__ == "__main__":
    names = json.loads((CATALOG / "noms_affichage_fr.json").read_text(encoding="utf-8"))
    df = pd.read_csv(CATALOG / "catalogue_cultures_v6.csv", low_memory=False)
    df.columns = [c.lower() for c in df.columns]
    df = df[df.scientificname.isin(names)].drop_duplicates("ecoportcode").copy()
    # Noms français d'abord ("Fève / féverole" -> "Fève", "féverole"), puis les noms d'origine.
    fr = df.scientificname.map(lambda s: ", ".join(p.strip() for p in names[s].split("/")))
    df["comname"] = fr + ", " + df.comname.fillna("")
    df["n_fixer"] = df.n_fixer.map({True: 1, False: 0, "True": 1, "False": 0})
    OUT.mkdir(exist_ok=True)
    csv_path = OUT / "cultures_catalogue_v6.csv"
    df[COLUMNS].to_csv(csv_path, index=False)
    manifest = {
        "source": "Catalogue cultures v6 (EcoCrop + FAO-56 + AquaCrop)",
        "source_reference": "data/catalog/catalogue_cultures_v6.csv ; sources détaillées dans data/catalog/sources.csv",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "method": "Filtrage des cultures de noms_affichage_fr.json, colonnes du contrat bd/connection.py",
        "dataset_version": "v6",
        "units": UNITS,
    }
    (OUT / "manifest_catalogue_v6.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(df)} cultures -> {csv_path}")
