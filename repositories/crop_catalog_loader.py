"""Import des fichiers du catalogue (CSV) dans PostgreSQL.

Usage : python -m repositories.crop_catalog_loader
Les noms de fichiers viennent de `settings` (configurables par variables d'environnement).
"""
import json
import math
from pathlib import Path

import pandas as pd
from sqlalchemy import delete
from sqlalchemy.orm import Session

from models import Crop, CropCalendar, DataSource
from repositories.database import SessionLocal
from settings import settings

ECOLOGY_COLUMNS = ["TOPMN", "TOPMX", "TMIN", "TMAX", "ROPMN", "ROPMX", "RMIN", "RMAX", "PHOPMN", "PHOPMX",
                   "PHMIN", "PHMAX", "KTMP", "TEXT", "TEXTR", "FER", "SAL", "SALR", "DRA", "DEP", "GMIN", "GMAX"]
SOURCE_COLUMNS = ["source_kc", "source_stades", "source_zr_p", "source_thermique", "statut_n_fixer",
                  "statut_thermique", "kc_convention", "fao56_region", "fao56_crop_name", "aquacrop_fichier"]


def _clean(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _float(value):
    value = _clean(value)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _int(value):
    value = _float(value)
    return int(value) if value is not None else None


def _bool(value):
    value = _clean(value)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "oui"}


def _load_display_names(catalog_dir: Path) -> dict[str, str]:
    path = catalog_dir / "noms_affichage_fr.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_catalog(session: Session, catalog_dir: Path | None = None) -> dict[str, int]:
    catalog_dir = catalog_dir or settings.catalog_dir
    crops_df = pd.read_csv(catalog_dir / settings.crop_catalog_file, low_memory=False)
    calendar_df = pd.read_csv(catalog_dir / settings.crop_calendar_file)
    display_names = _load_display_names(catalog_dir)

    session.execute(delete(CropCalendar))
    session.execute(delete(Crop))
    session.execute(delete(DataSource))

    crops_df = crops_df.drop_duplicates("EcoPortCode")
    for row in crops_df.to_dict("records"):
        scientific = row["ScientificName"]
        session.add(Crop(
            eco_port_code=int(row["EcoPortCode"]),
            scientific_name=scientific,
            display_name=display_names.get(scientific, scientific),
            common_names=_clean(row.get("COMNAME")),
            family=_clean(row.get("famille")),
            category=_clean(row.get("CAT")),
            life_span=_clean(row.get("LISPA")),
            n_fixer=_bool(row.get("n_fixer")),
            level=_clean(row.get("niveau")) or "3_ecocrop_seulement",
            ph_min=_float(row.get("ph_min")), ph_max=_float(row.get("ph_max")), ph_opt=_float(row.get("ph_opt")),
            kc_ini=_float(row.get("kc_ini")), kc_mid=_float(row.get("kc_mid")), kc_end=_float(row.get("kc_end")),
            stage_ini_days=_int(row.get("l_ini")), stage_dev_days=_int(row.get("l_dev")),
            stage_mid_days=_int(row.get("l_mid")), stage_late_days=_int(row.get("l_late")),
            root_depth_max_m=_float(row.get("zr_max_m")), depletion_fraction_p=_float(row.get("p_fao56")),
            t_base=_float(row.get("t_base")), t_upper=_float(row.get("t_upper")),
            gdd_maturity=_float(row.get("gdd_maturite")),
            gdd_yield_start=_float(row.get("gdd_debut_formation_rendement")),
            cycle_min_days=_float(row.get("GMIN")), cycle_max_days=_float(row.get("GMAX")),
            ecology={c: _clean(row.get(c)) for c in ECOLOGY_COLUMNS},
            sources={c: _clean(row.get(c)) for c in SOURCE_COLUMNS},
        ))
    session.flush()

    known_codes = set(crops_df["EcoPortCode"].astype(int))
    calendar_df = calendar_df.dropna(subset=["EcoPortCode"])
    calendar_count = 0
    for row in calendar_df.to_dict("records"):
        code = int(row["EcoPortCode"])
        if code not in known_codes:
            continue
        session.add(CropCalendar(
            eco_port_code=code, country=row["pays"], zone_id=str(row["zone_id"]).zfill(3),
            zone_name=row["zone_agroecologique"], usage=_clean(row.get("usage_ou_conduite")),
            sow_start_month=int(row["semis_debut_mois"]), sow_start_day=int(row["semis_debut_jour"]),
            sow_end_month=int(row["semis_fin_mois"]), sow_end_day=int(row["semis_fin_jour"]),
            harvest_start_month=int(row["recolte_debut_mois"]), harvest_start_day=int(row["recolte_debut_jour"]),
            harvest_end_month=int(row["recolte_fin_mois"]), harvest_end_day=int(row["recolte_fin_jour"]),
            source=row["source_calendrier"],
        ))
        calendar_count += 1

    sources_path = catalog_dir / settings.catalog_sources_file
    source_count = 0
    if sources_path.exists():
        for row in pd.read_csv(sources_path).to_dict("records"):
            session.add(DataSource(source_id=row["source_id"], reference=row["reference"], url=_clean(row.get("url")),
                                   accessed_on=_clean(row.get("consulte_le")), used_for=_clean(row.get("utilise_pour"))))
            source_count += 1

    session.commit()
    return {"crops": len(crops_df), "calendars": calendar_count, "sources": source_count}


if __name__ == "__main__":
    with SessionLocal() as db:
        print(load_catalog(db))
