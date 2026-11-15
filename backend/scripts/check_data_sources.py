"""Vérifie en direct chaque source de données (à lancer sur ton PC, avec Internet).

    python scripts/check_data_sources.py            # test en lecture seule, rien n'est écrit
    python scripts/check_data_sources.py --store    # collecte + stockage dans MySQL (external_agri_datasets)
    python scripts/check_data_sources.py --gee      # teste aussi Earth Engine (GPM, SMAP, MODIS)

Coordonnées de test : Kairouan (35.68 N, 10.10 E).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

LAT, LON = 35.68, 10.10


def run(name, fn):
    t0 = time.time()
    try:
        detail = fn()
        print(f"[OK]     {name:28} {detail}  ({time.time() - t0:.1f}s)")
        return True
    except Exception as exc:  # on veut voir toutes les erreurs, source par source
        print(f"[ECHEC]  {name:28} {type(exc).__name__}: {str(exc)[:160]}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--store", action="store_true", help="enregistrer les collectes dans MySQL")
    parser.add_argument("--gee", action="store_true", help="tester aussi Google Earth Engine")
    args = parser.parse_args()

    from app.integrations.agri_external_data_collector import collector as c

    print("== Sources API (pipeline données externes) ==")
    tests = {
        "world_bank_tunisia_agriculture": (lambda: c._world_bank("AG.YLD.CREL.KG", 30, {"date": "2015:2024"}), None, {"date": "2015:2024"}),
        "nasa_power_point": (lambda: c._power({"latitude": LAT, "longitude": LON, "start": "2024-01-01", "end": "2024-01-07"}, 30),
                             None, {"latitude": str(LAT), "longitude": str(LON), "start": "2024-01-01", "end": "2024-01-07"}),
        "soilgrids_profile": (lambda: c._soilgrids({"latitude": LAT, "longitude": LON}, 60),
                              None, {"latitude": str(LAT), "longitude": str(LON)}),
        "faostat_crop_production": (lambda: c._faostat({"area_code": "216", "limit": "5"}, 60), None, {"area_code": "216", "limit": "5"}),
    }
    ok = 0
    for source_id, (fetch, indicators, params) in tests.items():
        def check(fetch=fetch):
            records, url, _ = fetch()
            sample = records[0] if records else {}
            value = sample.get("values") or sample.get("value") or sample.get("Value")
            return f"{len(records)} enregistrement(s), ex. {str(value)[:70]}"
        ok += run(source_id, check)
        if args.store:
            run(f"  -> MySQL {source_id}", lambda s=source_id, i=indicators, p=params: (
                lambda d: f"dataset {d['dataset_id'][:8]}… ({d['record_count']} lignes"
                          f"{', déjà présent' if d.get('duplicate_detected') else ''})")(c.collect_source(s, i, p)))

    if args.store:
        run("Etat du pipeline", lambda: (lambda s: f"{s['database_dataset_count']} dataset(s) en base, "
                                                   f"{s['datasets_by_quality_status']}")(c.pipeline_status()))

    print("\n== Catalogue cultures (MySQL nasa_challenge.culture) ==")
    from bd.cultures import get_culture, lister_cultures
    run("lister_cultures", lambda: f"{len(lister_cultures())} culture(s)")
    run("get_culture('orge')", lambda: get_culture("orge")["nom_scientifique"])

    if args.gee:
        print("\n== Google Earth Engine (moteur d'indicateurs) ==")
        from app.core.config import settings
        from common import connectors as cn
        if not run("init_gee", lambda: (cn.init_gee(settings.gee_project, settings.gee_service_account or None,
                                                    settings.gee_key_file or None), settings.gee_project)[1]):
            return 1
        run("GPM IMERG (pluie/jour)", lambda: f"{len(cn.fetch_gpm_daily(LAT, LON, '2024-01-01', '2024-01-08'))} jour(s)")
        run("SMAP L4 (humidité sol)", lambda: f"{len(cn.fetch_smap(LAT, LON, '2024-01-01', '2024-01-08'))} ligne(s)")
        run("MODIS MOD13Q1 (NDVI)", lambda: f"{len(cn.fetch_modis_vi(LAT, LON, '2024-01-01', '2024-03-01'))} image(s)")

    print(f"\n{ok}/4 sources API joignables.")
    return 0 if ok == 4 else 1


if __name__ == "__main__":
    raise SystemExit(main())
