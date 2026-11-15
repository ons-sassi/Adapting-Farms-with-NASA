"""Importe un catalogue de cultures après validation du manifeste et du schéma MySQL."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bd.config import DB_CONFIG, DB_NAME, TABLE_CULTURE
from bd.mysql_ingestor import ImportDatabaseError, MySQLIngestor

CSV = Path(__file__).resolve().parent / "data" / "cultures_completes_8_especes_v6.csv"
CULTURE_COLUMNS = {
    "ecoportcode", "scientificname", "comname", "famille", "saison", "n_fixer",
    "t_base", "t_upper", "gdd_maturite", "kc_mid", "kc_ini", "kc_end",
    "zr_mm", "ph_min", "ph_max", "ph_opt", "duree_cycle", "semis_mois",
    "semis_jour", "recolte_mois", "recolte_jour", "seuil_praticable",
}
CULTURE_REQUIRED_COLUMNS = {
    "ecoportcode", "scientificname", "comname", "famille",
    "t_base", "gdd_maturite", "kc_mid", "zr_mm", "ph_min", "ph_max",
}
CULTURE_EXPECTED_UNITS = {
    "t_base": "degC",
    "t_upper": "degC",
    "gdd_maturite": "degC_day",
    "kc_mid": "1",
    "kc_ini": "1",
    "kc_end": "1",
    "zr_mm": "mm",
    "ph_min": "pH",
    "ph_max": "pH",
    "ph_opt": "pH",
    "duree_cycle": "day",
}
CULTURE_NUMERIC_COLUMNS = set(CULTURE_EXPECTED_UNITS) | {
    "ecoportcode", "semis_mois", "semis_jour", "recolte_mois",
    "recolte_jour", "seuil_praticable",
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help=(
            "JSON de provenance incluant source, source_reference, collected_at, "
            "method, dataset_version et units"
        ),
    )
    args = parser.parse_args()
    if not CSV.is_file():
        parser.error(f"Fichier source absent: {CSV}")
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            parser.error("Le manifeste doit contenir un objet JSON.")
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"Manifeste illisible ou JSON invalide: {type(exc).__name__}")

    ingestor = MySQLIngestor(db_config=DB_CONFIG, database=DB_NAME)
    try:
        result = ingestor.ingest(
            CSV,
            table_name=TABLE_CULTURE,
            manifest=manifest,
            allowed_columns=CULTURE_COLUMNS,
            required_columns=CULTURE_REQUIRED_COLUMNS,
            key_columns=("ecoportcode",),
            expected_units=CULTURE_EXPECTED_UNITS,
            numeric_columns=CULTURE_NUMERIC_COLUMNS,
            integer_columns=("ecoportcode", "semis_mois", "semis_jour", "recolte_mois", "recolte_jour"),
            boolean_columns=("n_fixer",),
        )
    except (ImportDatabaseError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "committed":
        raise SystemExit(1)
