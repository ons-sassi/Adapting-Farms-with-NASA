"""Analyse de rotation pour le frontend : catalogue -> règles -> séquences -> scores.

Réutilise les moteurs existants :
- engine.rotation.exclusion_rules.evaluate_exclusion_rules (7 règles d'exclusion)
- engine.rotation.sequence_generator.generate_sequences (séquences pluriannuelles)
- engine.rotation.priority_weighting.calculate_weighted_score (priorités du fermier)

Les sous-scores qui exigent des données satellite (NDVI, ET0, GDD...) ne sont pas
inventés : sans ces données, ils sont estimés à partir du catalogue et marqués
comme tels (`dataQuality = "catalogue"`), ou laissés vides (dynamique végétative).
"""
from __future__ import annotations

import math
from datetime import date
from statistics import mean

from app.engine.rotation.exclusion_rules import evaluate_exclusion_rules
from app.engine.rotation.priority_weighting import DIMENSIONS, calculate_weighted_score
from app.engine.rotation.sequence_generator import generate_sequences
from app.services import frontend_catalog as catalog

WATER_SCORE = {"Faible": 1.0, "Moyen": 0.7, "Élevé": 0.4, "Inconnu": 0.55}
IRRIGATION_BONUS = {"none": 0.0, "drip": 0.15, "sprinkler": 0.3, "surface": 0.3, "other": 0.1}

# Priorités du frontend (curseurs 0–5) -> objectifs du moteur de pondération (0–100).
def map_priorities(p: dict) -> dict:
    g = lambda k: float(p.get(k, 0)) * 20  # noqa: E731
    return {
        "economie_eau": g("water"),
        "revenu": max(g("yield"), g("profit")),
        "fourrage": 0.0,
        "erosion": max(g("resilience"), g("sustainability")),
        "matiere_organique": max(g("soil"), g("sustainability")),
        "azote": max(g("soil"), g("pests")),
        "simplicite": 0.0,
    }

# Profils utilisés pour proposer 3 stratégies différentes.
STRATEGY_PROFILES = [
    ("user", "Recommandée selon vos priorités", None),
    ("water", "Économie d'eau", {"water": 5, "yield": 1, "soil": 2, "profit": 1, "resilience": 3, "pests": 1, "sustainability": 2}),
    ("soil", "Sol et résilience", {"water": 2, "yield": 1, "soil": 5, "profit": 1, "resilience": 4, "pests": 4, "sustainability": 4}),
    ("yield", "Rendement et rentabilité", {"water": 1, "yield": 5, "soil": 2, "profit": 5, "resilience": 2, "pests": 2, "sustainability": 1}),
]
MAX_ROTATIONS = 3  # l'interface compare 3 rotations


def next_campaign_start(today: date | None = None) -> date:
    """1er septembre de la campagne agricole en cours (sept. → août)."""
    today = today or date.today()
    return date(today.year if today.month >= 9 else today.year, 9, 1)


IRRIGATION_COVER = {"none": 0.0, "drip": 0.6, "sprinkler": 1.0, "surface": 1.0, "other": 0.3}
DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _cycle_months(sowing_mmdd: str, cycle_days: int) -> list[int]:
    m0 = int(sowing_mmdd[:2])
    return [((m0 - 1 + i) % 12) + 1 for i in range(max(1, math.ceil(cycle_days / 30)))]


def crop_climate_scores(crop: dict, sowing: str, climate: dict | None, irrigation: str) -> dict:
    """Scores eau / climat d'une culture à partir du climat NASA POWER de la parcelle.
    Renvoie None pour un score impossible à calculer (donnée manquante)."""
    if not climate:
        return {"eau": None, "climat": None, "heat_months": 0}
    monthly = {m["month"]: m for m in climate["monthly"]}
    months = _cycle_months(sowing, crop["cycleDays"])
    rows = [monthly[m] for m in months if monthly.get(m) and monthly[m]["et0_mm"] is not None]
    if not rows:
        return {"eau": None, "climat": None, "heat_months": 0}
    kc = crop.get("kcMid") or 1.0
    need = sum(kc * r["et0_mm"] for r in rows)
    rain = sum(0.8 * (r["rain_mm"] or 0) for r in rows)  # pluie efficace ~80 %
    supplied = rain + IRRIGATION_COVER.get(irrigation, 0.0) * max(0.0, need - rain)
    eau = max(0.0, min(1.0, supplied / need)) if need > 0 else None
    climat = None
    if crop.get("tBase") is not None and crop.get("gddMaturity"):
        gdd = sum(max(0.0, (r["tmean_c"] or 0) - crop["tBase"]) * DAYS[r["month"] - 1] for r in rows)
        ratio = gdd / crop["gddMaturity"]
        if ratio < 1.0:
            climat = max(0.0, (ratio - 0.5) * 1.4)
        elif ratio <= 1.35:
            climat = 1.0
        else:
            climat = max(0.4, 1.0 - 0.5 * (ratio - 1.35))
    heat = sum(1 for r in rows if (r["tmax_c"] or 0) >= 38)
    if climat is not None:
        climat = climat * math.exp(-0.08 * heat)
    return {"eau": eau, "climat": climat, "heat_months": heat}


def _subscores(seq: dict, crops: dict[str, dict], irrigation: str, soil_ph: float | None, zone: str | None,
               climate: dict | None = None):
    items = [crops[x["crop_id"]] for x in seq["sequence"]]
    windows = {x["crop_id"]: x["sowing_date"][5:] for x in seq["sequence"]}
    fao_zone = catalog.ZONE_TO_FAO.get(zone or "")
    per_crop = [crop_climate_scores(c, windows[c["id"]], climate, irrigation) for c in items]

    if all(p["eau"] is not None for p in per_crop):
        eau = mean(p["eau"] for p in per_crop)
    else:  # estimation catalogue (classe de besoin en eau)
        bonus = IRRIGATION_BONUS.get(irrigation, 0.0)
        eau = mean(min(1.0, WATER_SCORE[c["water"]] + bonus) for c in items)

    zone_scores = [1.0 if fao_zone and fao_zone in c["zones"] else 0.6 for c in items] if fao_zone else None
    climat_parts = []
    for i, p in enumerate(per_crop):
        if p["climat"] is not None:
            climat_parts.append(p["climat"])
        elif zone_scores:
            climat_parts.append(zone_scores[i])
    climat = mean(climat_parts) if climat_parts else None

    legumes = sum(1 for c in items if c["nFixer"])
    fert = min(1.0, 0.45 + 0.15 * legumes)
    if soil_ph is not None:
        fits = [max(0.0, 1 - abs(soil_ph - c["phOpt"]) / 1.5) for c in items if c["phOpt"]]
        if fits:
            fert = 0.5 * fert + 0.5 * mean(fits)
    erosion = max(0.0, min(1.0, 0.8 - 0.2 * sum(c["tuber"] for c in items) + 0.1 * sum(c["coverCrop"] for c in items)))
    return {
        "eau": round(eau, 4),
        "climat_thermique": round(climat, 4) if climat is not None else None,
        "fertilite_sol": round(fert, 4),
        "protection_erosion": round(erosion, 4),
        "dynamique_vegetative": None,  # dépend de la parcelle, pas de la rotation (NDVI MODIS affiché à part)
        "compatibilite_succession": seq["mean_succession_compatibility"],
    }, per_crop


def _texts(items: list[dict], sub: dict, irrigation: str, unknown_rules: list[str], window_notes: list[str]):
    pros, cons, risks = [], [], []
    legumes = [c["name"] for c in items if c["nFixer"]]
    if legumes:
        pros.append(f"{len(legumes)} légumineuse(s) ({', '.join(dict.fromkeys(legumes))}) : apport d'azote")
    if len({c["family"] for c in items}) == len(items):
        pros.append("Familles botaniques toutes différentes : cycles de ravageurs rompus")
    if sub["eau"] >= 0.7:
        pros.append("Besoin en eau compatible avec l'irrigation de la parcelle")
    thirsty = [c["name"] for c in items if c["water"] == "Élevé"]
    if thirsty and irrigation == "none":
        cons.append(f"Cultures exigeantes en eau en pluvial : {', '.join(dict.fromkeys(thirsty))}")
    tubers = [c["name"] for c in items if c["tuber"]]
    if tubers:
        cons.append(f"Récolte souterraine ({', '.join(tubers)}) : sol nu, risque d'érosion")
    if sub["compatibilite_succession"] < 0.5:
        cons.append("Successions peu complémentaires (azote / profondeur racinaire)")
    if unknown_rules:
        risks.append("Règles non vérifiables sans données satellite pour : " + ", ".join(unknown_rules))
    risks.extend(window_notes)
    return pros, cons, risks


def run_analysis(request: dict, parcel: dict, soil_ph: float | None, today: date | None = None,
                 environment: dict | None = None) -> dict:
    """request = {crops, priorities, horizon, constraints}; parcel = dict au format frontend.
    environment = données de parcel_environment.collect() (NASA POWER, SoilGrids, ...) ou None."""
    environment = environment or {}
    climate = environment.get("climate")
    soil_source = "laboratoire / saisie" if soil_ph is not None else None
    if soil_ph is None and (environment.get("soil") or {}).get("ph") is not None:
        soil_ph, soil_source = environment["soil"]["ph"], "SoilGrids (estimation)"
    lab_ph = soil_source == "laboratoire / saisie"
    constraints = request.get("constraints") or {}
    forbidden = set(constraints.get("forbidden") or [])
    horizon = max(3, min(4, int(request.get("horizon") or 4)))
    irrigation = parcel.get("irrigationType", "none")
    zone = parcel.get("zone")
    previous_family = None
    if parcel.get("crop"):
        prev = next((c for c in catalog.list_crops() if c["name"].casefold() == parcel["crop"].casefold()), None)
        previous_family = prev["familyLatin"] if prev else None

    crops, candidates, excluded, unknown_rules, window_notes = {}, [], [], {}, {}
    for crop_id in request.get("crops") or []:
        crop = catalog.get_crop(crop_id)
        if crop is None:
            excluded.append({"id": crop_id, "name": crop_id, "reason": "Culture absente du catalogue"})
            continue
        if crop_id in forbidden:
            excluded.append({"id": crop_id, "name": crop["name"], "reason": "Interdite par l'agriculteur"})
            continue
        if not crop["eligible"]:
            excluded.append({"id": crop_id, "name": crop["name"], "reason": "Culture pérenne ou cycle inconnu"})
            continue
        engine_crop = {"nom": crop["name"], "code": crop["code"], "famille": crop["familyLatin"], "ph_opt": crop["phOpt"]}
        rules = evaluate_exclusion_rules(engine_crop, {
            # Exclusion stricte par le pH seulement avec une mesure du sol (pas une estimation SoilGrids).
            "soil_ph": soil_ph if lab_ph else None,
            "traits": {"root_or_tuber_crop": crop["tuber"]},
        })
        failed = [r for r in rules["regles"] if r["status"] == "FAIL"]
        if failed:
            excluded.append({"id": crop_id, "name": crop["name"], "reason": failed[0]["reason"]})
            continue
        if rules["statut_global"] != "PASS":
            unknown_rules[crop_id] = crop["name"]
        if soil_ph is not None and not lab_ph and crop["phOpt"] and abs(soil_ph - crop["phOpt"]) >= 1.5:
            window_notes[crop_id + ":ph"] = (f"{crop['name']} : pH estimé {soil_ph} loin de l'optimum {crop['phOpt']} "
                                             "(à confirmer par une analyse de sol)")
        start, end, origin = catalog.sowing_window(crop, zone)
        if not origin.startswith("calendrier FAO (zone"):
            window_notes[crop_id] = f"{crop['name']} : semis {start} → {end} ({origin})"
        crops[crop_id] = crop
        candidates.append({
            "name": crop_id, "code": crop["code"], "family": crop["familyLatin"],
            "n_fixer": crop["nFixer"], "root_depth_m": crop["rootDepthM"], "kc_ini": crop["kcIni"],
            # Les règles inconnues ne bloquent pas la démonstration ; elles sont signalées en risque.
            "rule_status": "PASS", "rule_reason": rules["interpretation"],
            "sowing_window_start": start, "sowing_window_end": end,
            "cycle_days": crop["cycleDays"], "underground_harvest": crop["tuber"],
        })

    sources = ["Catalogue cultures (EcoCrop, FAO-56, AquaCrop)", "Calendrier cultural FAO Tunisie"]
    if climate:
        sources.append(f"NASA POWER {climate['year']} (pluie, températures, ET0)")
    if soil_source:
        sources.append(f"pH du sol : {soil_source}")
    result_base = {
        "horizon": horizon, "excludedCrops": excluded,
        "dataQuality": "mesures" if climate else "catalogue", "dataSources": sources,
        "soilPh": soil_ph, "environmentErrors": environment.get("errors") or {},
        "dimensions": list(DIMENSIONS), "startDate": None, "rotations": [], "recommendedId": None,
    }
    if len(candidates) < 2:
        result_base["notice"] = "Au moins 2 cultures éligibles sont nécessaires pour construire une rotation."
        return result_base

    start_date = next_campaign_start(today)
    generated = generate_sequences(
        candidates=candidates, horizon=horizon, start_date=start_date, max_sequences=200,
        sensitive_years=4, min_gap=15, initial_soc=None, initial_erosion=None,
    )
    sequences = generated["sequences"]
    if previous_family:
        # Règle 7 (rupture sanitaire) : la 1re campagne ne répète pas la famille précédente.
        kept = [s for s in sequences if s["sequence"][0]["family"].casefold() != previous_family.casefold()]
        if kept:
            sequences = kept
    result_base["startDate"] = start_date.isoformat()
    if not sequences:
        result_base["notice"] = generated.get("no_valid_sequence_reason") or generated.get("notice")
        return result_base

    for seq in sequences:
        for item in seq["sequence"]:
            item["crop_id"] = item["culture"]
        seq["sub"], seq["per_crop"] = _subscores(seq, crops, irrigation, soil_ph, zone, climate)

    user_priorities = request.get("priorities") or {}
    rotations, used = [], set()
    for key, label, profile in STRATEGY_PROFILES:
        weights_src = map_priorities(profile or user_priorities)
        if not any(weights_src.values()):
            weights_src = map_priorities({k: 3 for k in ("water", "yield", "soil", "resilience")})
        ranked = sorted(sequences, key=lambda s: calculate_weighted_score(weights_src, s["sub"], 0)["score_provisoire"] or 0, reverse=True)
        best = next((s for s in ranked if tuple(x["crop_id"] for x in s["sequence"]) not in used), None)
        if best is None:
            continue
        if len(rotations) >= MAX_ROTATIONS:
            break
        used.add(tuple(x["crop_id"] for x in best["sequence"]))
        user_score = calculate_weighted_score(map_priorities(user_priorities) if any(map_priorities(user_priorities).values()) else weights_src, best["sub"], 0)
        items = [crops[x["crop_id"]] for x in best["sequence"]]
        ids = list(dict.fromkeys(x["crop_id"] for x in best["sequence"]))
        notes = [v for k, v in window_notes.items() if k.split(":")[0] in ids]
        hot = [c["name"] for c, p in zip(items, best["per_crop"]) if p["heat_months"]]
        if hot:
            notes.append("Fortes chaleurs (≥ 38 °C) pendant le cycle de : " + ", ".join(dict.fromkeys(hot)))
        dry = [c["name"] for c, p in zip(items, best["per_crop"]) if p["eau"] is not None and p["eau"] < 0.5]
        if dry:
            notes.append("Déficit hydrique probable (pluie + irrigation < 50 % du besoin) : " + ", ".join(dict.fromkeys(dry)))
        pros, cons, risks = _texts(items, best["sub"], irrigation,
                                   [unknown_rules[i] for i in ids if i in unknown_rules], notes)
        rotations.append({
            "id": f"r{len(rotations) + 1}", "name": label, "strategy": key,
            "score": round((user_score["score_provisoire"] or 0) * 100),
            "years": [x["crop_id"] for x in best["sequence"]],
            "calendar": [{"crop": x["crop_id"], "sowing": x["sowing_date"], "harvest": x["harvest_date"]} for x in best["sequence"]],
            "indices": {d: (round(v * 100) if v is not None else None) for d, v in best["sub"].items()},
            "coverage": user_score["couverture_ponderation"],
            "pros": pros, "cons": cons, "risks": risks,
            "explanation": (
                f"Séquence {' → '.join(c['name'] for c in items)} : compatibilité de succession "
                f"{round(best['sub']['compatibilite_succession'] * 100)} %, "
                f"{sum(1 for c in items if c['nFixer'])} légumineuse(s). Score calculé selon vos priorités "
                f"sur {round(user_score['couverture_ponderation'] * 100)} % des critères disponibles."
            ),
        })
    rotations[0]["name"] = STRATEGY_PROFILES[0][1]
    result_base["rotations"] = rotations
    result_base["recommendedId"] = max(rotations, key=lambda r: r["score"])["id"]
    return result_base
