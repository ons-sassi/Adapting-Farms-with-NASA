"""Générateur déterministe de séquences de rotation.

Applique les contraintes calendaires, sanitaires, azotées et racinaires du PDF
« Les Règles ». Les données absentes ne sont pas remplacées par des hypothèses.
"""
from __future__ import annotations
from datetime import date, timedelta
from itertools import product
from typing import Any

SENSITIVE_FAMILIES = {"solanaceae", "compositae", "asteraceae", "chenopodiaceae"}
TWO_YEAR_FAMILIES = {"gramineae", "poaceae", "leguminosae", "fabaceae"}

def norm_family(value):
    return " ".join(str(value or "").casefold().replace("_", " ").split())

def _date_in_year(mmdd: str, year: int) -> date:
    month, day = map(int, mmdd.split("-"))
    return date(year, month, day)

def _window_after(candidate: dict, earliest: date) -> date | None:
    """Première date de début de fenêtre située après earliest, dans les 18 mois."""
    for year in (earliest.year, earliest.year + 1):
        start = _date_in_year(candidate["sowing_window_start"], year)
        end = _date_in_year(candidate["sowing_window_end"], year)
        if end < start:
            end = _date_in_year(candidate["sowing_window_end"], year + 1)
        if start >= earliest and start <= end:
            return start
        if start < earliest <= end:
            return earliest
    return None

def _return_years(family: str, sensitive_years: int) -> int | None:
    f = norm_family(family)
    if f in SENSITIVE_FAMILIES:
        return sensitive_years
    if f in TWO_YEAR_FAMILIES:
        return 2
    return None

def _family_compatible(sequence: list[dict], candidate: dict, sensitive_years: int):
    family = norm_family(candidate["family"])
    if not family:
        return False, "Famille botanique inconnue."
    if sequence and norm_family(sequence[-1]["family"]) == family:
        return False, "Répétition consécutive de la même famille botanique."
    interval = _return_years(family, sensitive_years)
    for previous in sequence:
        if norm_family(previous["family"]) == family:
            if interval is None:
                return False, f"Délai de retour non défini pour la famille répétée « {candidate['family']} »."
            gap = candidate["campaign"] - previous["campaign"]
            if gap < interval:
                return False, f"Famille {candidate['family']} : retour après {gap} campagne(s), minimum {interval}."
    return True, None

def _succession_score(previous: dict | None, current: dict) -> float:
    """Formule exacte B_N + B_R du PDF, base neutre 0.50."""
    score = 0.50
    if previous is not None:
        prev_fix, cur_fix = previous.get("n_fixer"), current.get("n_fixer")
        if prev_fix is True and cur_fix is False:
            score += 0.30
        elif prev_fix is False and cur_fix is False:
            score -= 0.15
        prev_depth, cur_depth = previous.get("root_depth_m"), current.get("root_depth_m")
        if prev_depth is not None and cur_depth is not None and abs(cur_depth-prev_depth) >= 0.5:
            score += 0.15
    return max(0.0, min(1.0, score))

def generate_sequences(candidates: list[dict], horizon: int, start_date: date,
                       max_sequences: int, sensitive_years: int,
                       min_gap: int, initial_soc: float | None,
                       initial_erosion: float | None):
    eligible = [c for c in candidates if c["rule_status"] == "PASS"]
    excluded = [
        {"culture": c["name"], "code": c["code"], "status": c["rule_status"],
         "reason": c["rule_reason"]}
        for c in candidates if c["rule_status"] != "PASS"
    ]
    if not eligible:
        return {"sequences": [], "excluded_cultures": excluded,
                "notice": "Aucune culture n'a franchi les sept règles en PASS."}

    sequences = []
    # Beam-search-like expansion. Keep a bounded diverse set at each depth.
    beam = [[]]
    for campaign in range(horizon):
        expanded = []
        for seq in beam:
            previous = seq[-1] if seq else None
            prev_harvest = None if previous is None else date.fromisoformat(previous["harvest_date"])
            earliest = start_date if previous is None else prev_harvest + timedelta(days=min_gap)
            for crop in eligible:
                ok, reason = _family_compatible(seq, {**crop, "campaign": campaign}, sensitive_years)
                if not ok:
                    continue
                sow = _window_after(crop, earliest)
                if sow is None:
                    continue
                harvest = sow + timedelta(days=crop["cycle_days"])
                if previous and (sow - prev_harvest).days < min_gap:
                    continue
                item = {
                    "campaign": campaign,
                    "culture": crop["name"],
                    "code": crop["code"],
                    "family": crop["family"],
                    "n_fixer": crop["n_fixer"],
                    "root_depth_m": crop["root_depth_m"],
                    "sowing_date": sow.isoformat(),
                    "harvest_date": harvest.isoformat(),
                    "cycle_days": crop["cycle_days"],
                    "underground_harvest": crop["underground_harvest"],
                    "kc_ini": crop.get("kc_ini"),
                    "succession_score": _succession_score(previous, crop),
                }
                expanded.append(seq + [item])
        # deduplicate by culture-code path; prioritize mean succession compatibility
        expanded.sort(key=lambda s: sum(x["succession_score"] for x in s)/len(s), reverse=True)
        seen, beam = set(), []
        for seq in expanded:
            key = tuple(x["code"] for x in seq)
            if key in seen:
                continue
            seen.add(key)
            beam.append(seq)
            if len(beam) >= max(100, max_sequences * 40):
                break
        if not beam:
            break
    valid = []
    fixer_candidates_survived = any(c["n_fixer"] is True for c in eligible)
    for seq in beam:
        if len(seq) != horizon:
            continue
        if fixer_candidates_survived and horizon >= 3 and not any(x["n_fixer"] is True for x in seq):
            continue
        depths = [x["root_depth_m"] for x in seq if x["root_depth_m"] is not None]
        if len(depths) != horizon or max(depths)-min(depths) < 0.6:
            continue
        soc = initial_soc
        erosion = initial_erosion
        state_updates = []
        for i, item in enumerate(seq):
            if soc is not None:
                if item["n_fixer"] is True:
                    soc = min(1.0, soc + 0.12)
                elif item["n_fixer"] is False:
                    soc = max(0.0, soc - 0.06)
            if erosion is not None and item["underground_harvest"] is True:
                erosion = min(1.0, erosion + 0.10)
                if i + 1 < len(seq) and seq[i+1].get("kc_ini") is not None and seq[i+1]["kc_ini"] >= 0.60:
                    erosion = max(0.0, erosion - 0.10)
            state_updates.append({"campaign": i+1, "soc_norm_after_harvest": soc,
                                  "erosion_risk_after_harvest": erosion})
        valid.append({
            "sequence": seq,
            "mean_succession_compatibility": round(sum(x["succession_score"] for x in seq)/len(seq), 4),
            "root_depth_amplitude_m": round(max(depths)-min(depths), 3),
            "state_updates": state_updates,
        })
    valid.sort(key=lambda x: x["mean_succession_compatibility"], reverse=True)
    return {
        "sequences": valid[:max_sequences],
        "excluded_cultures": excluded,
        "candidates_passed_rules": len(eligible),
        "fixing_legume_quota_required": bool(fixer_candidates_survived and horizon >= 3),
        "notice": (
            "Le classement utilise uniquement le score de synergie de succession défini dans le document. "
            "Ce n'est pas le score agronomique global, qui sera calculé dans une API de scoring dédiée."
        ),
        "no_valid_sequence_reason": (
            None if valid else
            "Aucune séquence ne satisfait simultanément le calendrier, les délais sanitaires, "
            "le quota de légumineuses fixatrices et l'amplitude racinaire minimale de 0,6 m."
        ),
    }
