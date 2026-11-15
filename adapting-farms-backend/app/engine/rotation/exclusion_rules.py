"""Moteur déterministe des 7 règles d'exclusion décrites dans 'Les Règles'.

Aucune valeur manquante n'est estimée. Chaque règle retourne PASS, FAIL ou UNKNOWN.
"""
from __future__ import annotations
from datetime import timedelta
from typing import Any

PASS, FAIL, UNKNOWN = "PASS", "FAIL", "UNKNOWN"

def _result(rule: int, name: str, status: str, reason: str, **extra) -> dict[str, Any]:
    return {"rule": rule, "name": name, "status": status, "reason": reason, **extra}

def _tri_and(values: list[bool | None]) -> bool | None:
    """AND à trois états: False prévaut, puis inconnu, sinon True."""
    if any(v is False for v in values):
        return False
    if any(v is None for v in values):
        return None
    return True

def _workable_count(days: list[dict], saturation_threshold: float):
    workable, incomplete = 0, 0
    for item in days:
        saturation = item.get("surface_saturation")
        temp_k = item.get("surface_temp_k")
        if saturation is None or temp_k is None:
            incomplete += 1
            continue
        if saturation < saturation_threshold and temp_k > 273.15:
            workable += 1
    return workable, incomplete

def evaluate_exclusion_rules(crop: dict, payload: dict) -> dict[str, Any]:
    traits = payload.get("traits") or {}
    family = crop.get("famille")
    results: list[dict[str, Any]] = []
    warnings: list[str] = []

    # 1. Cycle thermique
    ratio = payload.get("ratio_gdd")
    if ratio is None:
        results.append(_result(1, "cycle_thermique", UNKNOWN, "Ratio_GDD absent."))
    elif ratio < 1.0:
        results.append(_result(1, "cycle_thermique", FAIL, f"Ratio_GDD={ratio} < 1.0 : cycle thermique insuffisant."))
    else:
        note = "Zone optimale selon le document." if 1.05 <= ratio <= 1.30 else "Culture thermiquement validée."
        if ratio > 1.60:
            note = "Ratio > 1.60 : maturation rapide ou possibilité de culture dérobée."
            warnings.append(note)
        elif ratio < 1.05 or ratio > 1.30:
            note = "Ratio accepté, mais hors zone optimale [1.05, 1.30]."
        results.append(_result(1, "cycle_thermique", PASS, note, ratio_gdd=ratio,
                               zone_optimale=1.05 <= ratio <= 1.30))

    # 2. Compatibilité pH. Le document définit le seuil létal par écart >= 1.5.
    ph, ph_opt, ph_score = payload.get("soil_ph"), crop.get("ph_opt"), payload.get("ph_score")
    if ph is None or ph_opt is None:
        results.append(_result(2, "compatibilite_ph", UNKNOWN,
                               "pH du sol ou pH optimal de la culture absent."))
    else:
        delta = abs(float(ph) - float(ph_opt))
        if delta >= 1.5 or ph_score == 0:
            results.append(_result(2, "compatibilite_ph", FAIL,
                                   f"Ecart |pH_sol - pH_opt|={delta:.2f} >= 1.5 : exclusion stricte.",
                                   ecart_ph=delta))
        else:
            if ph_score is not None and ph_score < 0.3:
                warnings.append("Score_pH < 0.3 : seuil de sécurité agronomique recommandé; validation experte conseillée.")
            results.append(_result(2, "compatibilite_ph", PASS,
                                   "Ecart de pH inférieur au seuil d'exclusion stricte.",
                                   ecart_ph=delta, score_ph_fourni=ph_score))

    # 3. Gel tardif: cuvette AND gel pendant/après début semis AND culture sensible.
    tpi = payload.get("tpi")
    frost = payload.get("last_spring_frost")
    sow_start = payload.get("sowing_window_start")
    sensitive_frost = traits.get("sensitive_to_late_frost")
    adjusted_frost = frost
    if tpi is not None and tpi < -5 and frost is not None:
        delay = payload.get("microclimate_frost_delay_days")
        if delay is None:
            warnings.append("TPI < -5 : marge microclimatique recommandée de +7 à +10 jours non renseignée; évaluation conservatrice sur la date brute.")
        else:
            adjusted_frost = frost + timedelta(days=delay)
    frost_condition = None if adjusted_frost is None or sow_start is None else adjusted_frost >= sow_start
    condition = _tri_and([
        None if tpi is None else tpi < 0,
        frost_condition,
        sensitive_frost,
    ])
    results.append(_result(3, "gel_tardif_microclimat",
                           FAIL if condition is True else PASS if condition is False else UNKNOWN,
                           "Cuvette + gel pendant/après le début du semis + culture sensible."
                           if condition is True else
                           "Au moins une condition cumulative d'exclusion est absente."
                           if condition is False else
                           "TPI, dates de gel/semis ou sensibilité au gel manquant.",
                           last_spring_frost_effective=adjusted_frost.isoformat() if adjusted_frost else None))

    # 4. Asphyxie racinaire: (TWI élevé OR RSM critique) AND culture sensible.
    twi, rsm = payload.get("twi_high"), payload.get("rsm_gt_1_critical_duration")
    sensitive_water = traits.get("sensitive_to_waterlogging")
    water_hazard = True if (twi is True or rsm is True) else (
        False if (twi is False and rsm is False) else None
    )
    if sensitive_water is False or water_hazard is False:
        status = PASS
    elif sensitive_water is True and water_hazard is True:
        status = FAIL
    else:
        status = UNKNOWN
    reason = ("Risque TWI/RSM et sensibilité biologique réunis."
              if status == FAIL else
              "Les conditions d'exclusion ne sont pas réunies."
              if status == PASS else
              "TWI, RSM critique ou sensibilité à l'excès d'eau manquant.")
    results.append(_result(4, "asphyxie_racinaire_exces_eau", status, reason))

    # 5. Argile > 0.35 AND culture racine/tubercule.
    clay, root_crop = payload.get("clay_ratio"), traits.get("root_or_tuber_crop")
    if clay is None or root_crop is None:
        status = PASS if (clay is not None and clay <= 0.35) or root_crop is False else UNKNOWN
    else:
        status = FAIL if clay > 0.35 and root_crop else PASS
    results.append(_result(5, "texture_sol_recolte", status,
                           "Clay_Ratio > 0.35 et culture racine/tubercule."
                           if status == FAIL else
                           "Les conditions cumulatives d'exclusion ne sont pas réunies."
                           if status == PASS else
                           "Clay_Ratio ou type biologique racine/tubercule manquant.",
                           clay_ratio=clay))

    # 6. Practicabilité au semis ET à la récolte.
    sow_days = payload.get("sowing_workability_days") or []
    harv_days = payload.get("harvest_workability_days") or []
    sat_threshold = payload.get("surface_saturation_max_threshold")
    n_min = payload.get("n_min_chantier")
    if sat_threshold is None or n_min is None or not sow_days or not harv_days:
        results.append(_result(6, "praticabilite_mecanique", UNKNOWN,
                               "Seuil de saturation, N_min ou observations quotidiennes semis/récolte manquants."))
    else:
        sow_count, sow_incomplete = _workable_count(sow_days, sat_threshold)
        harv_count, harv_incomplete = _workable_count(harv_days, sat_threshold)
        sow_status = PASS if sow_count >= n_min else (UNKNOWN if sow_incomplete else FAIL)
        harv_status = PASS if harv_count >= n_min else (UNKNOWN if harv_incomplete else FAIL)
        if FAIL in (sow_status, harv_status):
            status = FAIL
        elif UNKNOWN in (sow_status, harv_status):
            status = UNKNOWN
        else:
            status = PASS
        results.append(_result(6, "praticabilite_mecanique", status,
                               "Nombre de jours praticables insuffisant dans au moins une fenêtre."
                               if status == FAIL else
                               "Nombre de jours praticables suffisant au semis et à la récolte."
                               if status == PASS else
                               "Observations incomplètes : praticabilité non confirmée.",
                               jours_praticables_semis=sow_count,
                               jours_praticables_recolte=harv_count,
                               n_min_chantier=n_min,
                               jours_incomplets_semis=sow_incomplete,
                               jours_incomplets_recolte=harv_incomplete))

    # 7. Rupture sanitaire: same family consecutive OR VCI decline + family in previous 2 seasons.
    previous = payload.get("previous_families") or []
    normalized_family = str(family).strip().casefold() if family else None
    normalized_previous = [str(x).strip().casefold() if x else None for x in previous]
    vci_decline = payload.get("vci_decline_despite_normal_weather")
    if normalized_family is None or not normalized_previous:
        status = UNKNOWN
        reason = "Famille botanique ou historique des familles précédentes absent."
    elif normalized_previous[0] == normalized_family:
        status, reason = FAIL, "Même famille botanique que la culture immédiatement précédente."
    elif vci_decline is True and normalized_family in normalized_previous[:2]:
        status, reason = FAIL, "Déclin VCI malgré météo normale et famille présente dans les deux dernières saisons."
    elif vci_decline is None and normalized_family in normalized_previous[:2]:
        status, reason = UNKNOWN, "Famille présente dans les deux dernières saisons, mais signal VCI inconnu."
    elif normalized_previous[0] is None:
        status, reason = UNKNOWN, "Famille de la saison immédiatement précédente inconnue."
    else:
        status, reason = PASS, "Pas de répétition familiale immédiate ni d'alerte VCI confirmée."
    results.append(_result(7, "rupture_sanitaire", status, reason,
                           famille_culture=family, familles_precedentes=previous))

    statuses = [r["status"] for r in results]
    overall = FAIL if FAIL in statuses else UNKNOWN if UNKNOWN in statuses else PASS
    return {
        "culture": crop.get("nom_scientifique") or crop.get("nom"),
        "culture_code": crop.get("code"),
        "famille_botanique": family,
        "statut_global": overall,
        "eligible_pour_scoring": overall == PASS,
        "nombre_regles": len(results),
        "regles": results,
        "avertissements": warnings,
        "interpretation": (
            "Culture rejetée : au moins une règle d'exclusion échoue."
            if overall == FAIL else
            "Évaluation incomplète : ne pas considérer la culture comme validée."
            if overall == UNKNOWN else
            "Les sept règles sont satisfaites; la culture peut passer au sous-scoring."
        ),
        "source_regles": "Document utilisateur « Les Règles », règles d'exclusion 1 à 7.",
    }
