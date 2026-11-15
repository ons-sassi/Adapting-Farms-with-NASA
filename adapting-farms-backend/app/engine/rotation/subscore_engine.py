"""Calcul déterministe des six sous-scores décrits dans « les règles.pdf ».
Aucune valeur manquante n'est imputée. Les poids du score global ne sont pas
fixés ici car le document source indique qu'ils doivent être définis séparément.
"""
from __future__ import annotations
from math import exp
from typing import Any

DIMENSIONS = ("eau", "climat_thermique", "fertilite_sol", "protection_erosion", "dynamique_vegetative", "compatibilite_succession")

def clip(value: float, low: float=0.0, high: float=1.0) -> float:
    return max(low, min(high, float(value)))

def _missing(obj: dict, keys: tuple[str, ...]) -> list[str]:
    return [k for k in keys if obj.get(k) is None]

def _water(common: dict, crop: dict) -> tuple[float|None, dict, list[str]]:
    h=common.get("hydrique", {}); missing=[]; diag={}
    keys=("et0_daily_mm", "effective_rainfall_mm", "awc_mm_per_m", "p_fao56", "rsm_ratio", "twi_norm", "northness")
    missing += [f"hydrique.{k}" for k in _missing(h,keys)]
    if crop.get("kc_daily") is None: missing.append("culture.kc_daily")
    if crop.get("root_depth_max_m") is None: missing.append("culture.root_depth_max_m")
    if missing: return None,diag,missing
    et0=h["et0_daily_mm"]; kc=crop["kc_daily"]
    if len(et0)!=len(kc): return None,{"erreur":"ET0 et Kc de longueurs différentes"},["hydrique.et0_daily_mm/culture.kc_daily"]
    etc=sum(float(k)*float(e) for k,e in zip(kc,et0))
    raw=h["p_fao56"]*(h["awc_mm_per_m"]*crop["root_depth_max_m"])
    if etc <= 0: return None,{"ETc_mm":etc,"RAW_mm":raw},["ETc doit être strictement positif"]
    bilan=clip((h["effective_rainfall_mm"]+h["rsm_ratio"]*raw)/etc)
    score=clip(.75*bilan+.15*h["twi_norm"]+.10*((h["northness"]+1)/2))
    diag={"ETc_mm":round(etc,4),"RAW_mm":round(raw,4),"I_bilan":round(bilan,6)}
    return score,diag,[]

def _thermal(common: dict, crop: dict) -> tuple[float|None,dict,list[str]]:
    t=common.get("thermique",{}); missing=[]
    for k in ("gdd_available","heat_days_after_yield_formation","cold_days_during_initial_phase"):
        if t.get(k) is None: missing.append(f"thermique.{k}")
    for k in ("gdd_maturity",):
        if crop.get(k) is None: missing.append(f"culture.{k}")
    if missing: return None,{},missing
    ratio=t["gdd_available"]/crop["gdd_maturity"]
    if ratio < 1.0:
        return None,{"ratio_GDD":round(ratio,6),"erreur":"Ratio_GDD < 1 : la culture aurait dû être exclue par la règle 1."},["incoherence_regle_exclusion_1"]
    if ratio < 1.05: igdd=(ratio-1.0)/.05
    elif ratio <= 1.35: igdd=1.0
    else: igdd=max(.40,1.0-.50*(ratio-1.35))
    score=igdd*exp(-.08*t["heat_days_after_yield_formation"]-.05*t["cold_days_during_initial_phase"])
    return clip(score),{"ratio_GDD":round(ratio,6),"I_GDD":round(igdd,6)},[]

def _soil(common:dict,crop:dict)->tuple[float|None,dict,list[str]]:
    s=common.get("sol",{}); missing=[]
    for k in ("ph_soil","exploitable_soil_depth_m","soc_norm"):
        if s.get(k) is None: missing.append(f"sol.{k}")
    for k in ("ph_min","ph_opt","ph_max","root_depth_max_m","n_fixer"):
        if crop.get(k) is None: missing.append(f"culture.{k}")
    if missing: return None,{},missing
    pmin,popt,pmax=crop["ph_min"],crop["ph_opt"],crop["ph_max"]
    if not pmin < popt < pmax: return None,{},["bornes_pH_invalides"]
    ph=s["ph_soil"]
    if ph < pmin or ph > pmax: ph_score=0.0
    elif ph <= popt: ph_score=(ph-pmin)/(popt-pmin)
    else: ph_score=(pmax-ph)/(pmax-popt)
    iprof=min(1.0,s["exploitable_soil_depth_m"]/crop["root_depth_max_m"])
    if crop["n_fixer"] is True: ifert=.70+.30*s["soc_norm"]
    else: ifert=s["soc_norm"]
    score=clip(.40*ph_score+.30*iprof+.30*ifert)
    return score,{"Score_pH":round(ph_score,6),"I_prof":round(iprof,6),"I_fert":round(ifert,6)},[]

def _erosion(common:dict,crop:dict)->tuple[float|None,dict,list[str]]:
    e=common.get("erosion",{}); missing=[]
    for k in ("ls_norm","rainfall_erosivity_norm"):
        if e.get(k) is None: missing.append(f"erosion.{k}")
    for k in ("kc_ini","underground_harvest"):
        if crop.get(k) is None: missing.append(f"culture.{k}")
    if missing: return None,{},missing
    hazard=.60*e["ls_norm"]+.40*e["rainfall_erosivity_norm"]
    pculture=clip(crop["kc_ini"]/.70-(.25 if crop["underground_harvest"] else 0.0))
    score=clip(1.0-hazard*(1.0-pculture))
    return score,{"E_parcelle":round(hazard,6),"P_culture":round(pculture,6)},[]

def _history(common:dict)->tuple[float|None,dict,list[str]]:
    h=common.get("historique",{}); keys=("vci_mean","evi_peak_trend_norm","esi_mean")
    missing=[f"historique.{k}" for k in _missing(h,keys)]
    if missing:return None,{},missing
    score=clip(.50*h["vci_mean"]+.30*((h["evi_peak_trend_norm"]+1)/2)+.20*h["esi_mean"])
    return score,{},[]

def _succession(crop:dict)->tuple[float|None,dict,list[str]]:
    previous=crop.get("previous_crops")
    if previous is None:return None,{},["culture.previous_crops"]
    if len(previous)==0:return .50,{"B_N":0.0,"B_R":0.0,"M_retour":0.0,"historique":"connu_vide"},[]
    if len(previous)<2:return None,{},["culture.previous_crops.c_t_2"]
    prev,prev2=previous[0],previous[1]
    if crop.get("n_fixer") is None or prev.get("n_fixer") is None:return None,{},["culture.n_fixer","culture.previous_crops[0].n_fixer"]
    if crop.get("root_depth_max_m") is None or prev.get("root_depth_max_m") is None:return None,{},["culture.root_depth_max_m","culture.previous_crops[0].root_depth_max_m"]
    if not crop.get("family") or not prev.get("family") or not prev2.get("family"):
        return None,{},["culture.family","culture.previous_crops.family"]
    bn=.30 if prev["n_fixer"] is True and crop["n_fixer"] is False else (-.15 if prev["n_fixer"] is False and crop["n_fixer"] is False else 0.0)
    br=.15 if abs(crop["root_depth_max_m"]-prev["root_depth_max_m"]) >= .5 else 0.0
    mretour=-.25 if str(crop["family"]).strip().casefold()==str(prev2["family"]).strip().casefold() else 0.0
    score=clip(.50+bn+br+mretour)
    return score,{"B_N":bn,"B_R":br,"M_retour":mretour},[]

def calculate_candidate_subscores(crop:dict, common:dict, provenance:dict|None=None)->dict:
    if str(crop.get("exclusion_status","")).upper()!="PASS":
        return {"identifiant":crop.get("identifiant"),"nom":crop.get("nom"),"statut":"NON_CALCULE_EXCLUSION_NON_PASS","sous_scores":{k:None for k in DIMENSIONS},"donnees_manquantes":["Les sept règles d'exclusion doivent être PASS avant le sous-scoring."],"diagnostics":{},"preuves":provenance or {}}
    calculators={"eau":_water,"climat_thermique":_thermal,"fertilite_sol":_soil,"protection_erosion":_erosion,"dynamique_vegetative":_history,"compatibilite_succession":_succession}
    scores={}; diagnostics={}; missing={}
    for key,fn in calculators.items():
        score,diag,miss=(fn(crop) if key=="compatibilite_succession" else (fn(common) if key=="dynamique_vegetative" else fn(common,crop)))
        scores[key]=round(score,6) if score is not None else None
        diagnostics[key]=diag
        if miss: missing[key]=miss
    available=sum(v is not None for v in scores.values())
    status="COMPLET" if available==len(DIMENSIONS) else ("PARTIEL" if available else "INSUFFISANT")
    return {"identifiant":crop["identifiant"],"nom":crop["nom"],"statut":status,"dimensions_disponibles":available,"dimensions_total":len(DIMENSIONS),"sous_scores":scores,"donnees_manquantes":missing,"diagnostics":diagnostics,"preuves":provenance or {},"notice":"Sous-scores calculés selon les formules du document « les règles.pdf ». Aucun poids global n'est appliqué ici."}

def calculate_rotation_subscores(payload:dict)->dict:
    common={k:payload.get(k,{}) for k in ("hydrique","thermique","sol","erosion","historique")}
    return {"methode":"six_sous_scores_deterministes_documentes","cultures":[calculate_candidate_subscores(c,common,payload.get("provenance",{})) for c in payload["cultures"]],"ponderation_globale":None,"notice_ponderation":"Le document source indique que les poids sont définis séparément par l'IA, sans fournir de valeurs numériques. Aucun score global pondéré n'est donc calculé par cette API."}
