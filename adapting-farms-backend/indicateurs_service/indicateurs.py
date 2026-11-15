"""
indicateurs.py : livrable « Personne A ».  Fonction principale :

    get_indicateurs(parcelle, culture="blé", start=None, end=None) -> dict

`donnees` (optionnel) = résultat de zonal_service.get_donnees_zonales(polygone, start, end) : données
brutes moyennées sur la parcelle, injectées à la place de la lecture au point. Sans `donnees`,
tout est lu au point (lat, lon). Un bloc zonal manquant retombe sur la lecture au point.

`parcelle` = {"lat": 35.68, "lon": 10.10, "surface_ha": 5,            # surface_ha optionnel
              "sol_mesure": {"sand": 30, "clay": 35, "soc": 9,        # optionnel (analyse labo)
                             "nitrogen": 0.9, "phh2o": 7.8, "bdod": 1.35}}

CONVENTION DES DATES (tout le projet) : `start` inclus, `end` EXCLU ([start, end[).
Les connecteurs GEE l'appliquent nativement ; NASA POWER (end inclusif côté API) est appelé
avec end - 1 jour ; les découpages de séries utilisent `_between`.

Chaque indice est renvoyé avec : valeur, unité, source, résolution, statut
("estimée" / "mesurée" / "mixte"), période. Les avertissements signalent les sources dont la
résolution est plus grossière que la parcelle, les périodes tronquées (latence des données)
et les blocs en erreur : un bloc qui échoue n'empêche pas les autres.

Les paramètres de culture ne sont plus codés en dur : ils sont lus dans MySQL (base nasa_challenge,
table culture) par bd.cultures.get_culture(). `culture` = nom, code EcoPort ou nom scientifique.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd

from bd.cultures import get_culture, lister_cultures
from common import connectors as cn
from common import indices as ix

# source -> (nom, résolution en mètres)
SOURCES = {
    "power":      ("NASA POWER (MERRA-2)", 50000),
    "smap":       ("SMAP L4 SPL4SMGP v8", 11000),
    # Les images IMERG V07 récentes sont `provisional` : la provenance exacte est dans
    # `statut_produit` de chaque indicateur, pas dans ce libellé.
    "gpm":        ("GPM IMERG V07", 11132),
    "modis_vi":   ("MODIS MOD13Q1", 250),
    "modis_refl": ("MODIS MOD09A1", 500),
    "modis_lst":  ("MODIS MOD11A2", 1000),
    "modis_et":   ("MODIS MOD16A2", 500),
    "srtm":       ("SRTM GL1", 30),
    "merit":      ("MERIT Hydro", 90),
    "soilgrids":  ("SoilGrids 2.0 (ISRIC)", 250),
}
SOL_KEYS = ["sand", "clay", "soc", "nitrogen", "phh2o", "bdod"]


# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #
def _num(v):
    """Convertit en type JSON sûr : NaN/inf -> None, numpy -> natif."""
    if v is None or isinstance(v, str):
        return v
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return None if (math.isnan(f) or math.isinf(f)) else round(f, 4)


def I(valeur, unite, src, statut="estimée", periode=None, note=None,
      statut_produit=None) -> dict:
    nom, res = SOURCES[src]
    d = {
        "valeur": _num(valeur),
        "unite": unite,
        "source": nom,
        "resolution_m": res,
        "statut": statut
    }
    if periode:
        d["periode"] = [str(p) for p in periode]
    if note:
        d["note"] = note
    if statut_produit:
        d["statut_produit"] = statut_produit
    return d


def _saison_par_defaut(crop: dict, today: dt.date):
    """Dernière saison complète (semis -> récolte) de la culture."""
    (sm, sd), (rm, rd) = crop["semis"], crop["recolte"]
    end = dt.date(today.year, rm, rd)
    if end > today:
        end = dt.date(today.year - 1, rm, rd)
    start_year = end.year - 1 if (sm, sd) > (rm, rd) else end.year
    return dt.date(start_year, sm, sd).isoformat(), end.isoformat()


def _resoudre_culture(culture) -> dict:
    """dict de paramètres : lu en base (nom / code / nom scientifique) ou dict déjà fourni."""
    return dict(culture) if isinstance(culture, dict) else get_culture(culture)


def saison(culture="blé"):
    """(start, end) de la dernière saison complète : à passer aussi à get_donnees_zonales."""
    return _saison_par_defaut(_resoudre_culture(culture), dt.date.today())


def _between(obj, start, end):
    """Lignes de `obj` (index temporel) dans [start, end[ : start inclus, end EXCLU."""
    idx = obj.index
    return obj[(idx >= pd.Timestamp(start)) & (idx < pd.Timestamp(end))]


def _src(ctx, cle, fetch, decouper=True):
    """Donnée injectée (service zonal) si disponible, sinon lecture au point via `fetch`."""
    v = ctx["donnees"].get(cle)
    if v is None:
        return fetch()
    if decouper and isinstance(v, pd.DataFrame):
        v = _between(v, ctx["start"], ctx["end"])
    return v


def _clip_end(ctx, key, collection_id):
    """Tronque la fin (EXCLUE) de la période au lendemain de la dernière date disponible de
    la collection GEE (`last_available` = date de la dernière image, donc incluse)."""
    last = cn.last_available(collection_id)
    last_excl = (pd.Timestamp(last) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    end_eff = min(ctx["end"], last_excl)
    if end_eff <= ctx["start"]:
        raise RuntimeError(f"{collection_id} : données disponibles seulement jusqu'au {last}, "
                           f"avant le début de la période ({ctx['start']}).")
    ctx["periodes"][key] = (ctx["start"], end_eff)
    return end_eff


# --------------------------------------------------------------------------- #
# Blocs par source
# --------------------------------------------------------------------------- #
def _sol(ctx) -> dict:
    lat, lon, crop, parcelle = ctx["lat"], ctx["lon"], ctx["crop"], ctx["parcelle"]
    mes = {k: float(v) for k, v in (parcelle.get("sol_mesure") or {}).items()
           if k in SOL_KEYS and v is not None}
    try:
        prof = _src(ctx, "sol", lambda: cn.fetch_soilgrids(lat, lon), decouper=False)
        soil = cn.soil_profile_mean(prof, crop["zr_mm"] / 10)
    except Exception:
        if len(mes) < len(SOL_KEYS):
            raise
        soil = pd.Series(mes, dtype=float)
    for k, v in mes.items():
        soil[k] = v
    statut = ("mesurée" if len(mes) == len(SOL_KEYS)
              else "mixte (mesurée + SoilGrids)" if mes else "estimée (SoilGrids)")
    ctx["statut_sol"] = statut

    om = ix.som_pct(soil["soc"])
    fc, pwp = ix.saxton_rawls(soil["sand"], soil["clay"], om)
    th_sat = ix.theta_sat(soil["bdod"])
    ctx.update(fc=fc, pwp=pwp, th_sat=th_sat)

    out = {}
    for k, u in [("sand", "%"), ("clay", "%"), ("silt", "%"), ("bdod", "g/cm3"),
                 ("soc", "g/kg"), ("nitrogen", "g/kg"), ("phh2o", "pH")]:
        if k in soil.index:
            out[k] = I(soil[k], u, "soilgrids", "mesurée" if k in mes else "estimée (SoilGrids)")
    ped = "estimée (pédotransfert Saxton-Rawls 2006)"
    out.update({
        "theta_FC": I(fc, "m3/m3", "soilgrids", ped),
        "theta_PWP": I(pwp, "m3/m3", "soilgrids", ped),
        "theta_SAT": I(th_sat, "m3/m3", "soilgrids", statut),
        "AWC_mm": I(ix.awc(fc, pwp, crop["zr_mm"]), "mm", "soilgrids", ped,
                    note=f"profondeur racinaire {crop['zr_mm']} mm"),
        "SOM_pct": I(om, "%", "soilgrids", statut),
        "Ratio_CN": I(ix.ratio_cn(soil["soc"], soil["nitrogen"]), "-", "soilgrids", statut),
        "Score_pH": I(ix.score_ph(soil["phh2o"], crop["ph_min"], crop["ph_max"], crop.get("ph_opt")), "0-1",
                      "soilgrids", statut,
                      note=f"plage culture {crop['ph_min']}-{crop['ph_max']} ({crop['source']})"),
        "Clay_Ratio": I(ix.clay_ratio(soil["clay"]), "-", "soilgrids", statut),
    })
    return out


def _power(ctx) -> dict:
    lat, lon, crop, start = ctx["lat"], ctx["lon"], ctx["crop"], ctx["start"]
    # POWER : `end` de l'API est INCLUSIF, alors que ctx["end"] est exclu -> end - 1 jour.
    # Latence POWER : ~2 jours.
    last_incl = min(pd.Timestamp(ctx["end"]) - pd.Timedelta(days=1),
                    pd.Timestamp(dt.date.today() - dt.timedelta(days=2)))
    if last_incl < pd.Timestamp(start):
        raise RuntimeError(f"NASA POWER : aucune donnée disponible avant le {start}.")
    end_api = last_incl.strftime("%Y-%m-%d")                                   # inclusif
    end_p = (last_incl + pd.Timedelta(days=1)).strftime("%Y-%m-%d")            # exclu (convention)
    ctx["periodes"]["power"] = (start, end_p)
    w = cn.fetch_power(lat, lon, start, end_api)
    et0 = ix.et0_fao56(w, lat, w.attrs.get("elevation", 0.0))
    p = (start, end_p)
    # Les cumuls pandas ignorent les NaN (-999 POWER) : on signale le nombre de jours concernés.
    n_nan = int(pd.concat([w["T2M_MAX"], w["T2M_MIN"], w["PRECTOTCORR"], et0], axis=1)
                .isna().any(axis=1).sum())
    if n_nan:
        ctx["avertissements"].append(
            f"NASA POWER : {n_nan} jour(s) avec valeur manquante, ignorés dans les cumuls "
            "(GDD, ET0, CWB...) : ces totaux sont sous-estimés.")

    cap = crop.get("t_upper") or 30.0
    g = ix.gdd(w["T2M_MAX"], w["T2M_MIN"], crop["tbase"], cap=cap)
    ratio, label = ix.gdd_ratio(g, crop["gdd_requis"])

    # Dernier gel de printemps : il faut les données depuis le 1er janvier de l'année de fin
    yr = last_incl.year
    w_year = cn.fetch_power(lat, lon, f"{yr}-01-01", end_api, parameters=["T2M_MIN"])
    lsf = ix.last_spring_frost(w_year["T2M_MIN"], yr)

    return {
        "GDD": I(g, "°C.jour", "power", periode=p, note=f"Tbase={crop['tbase']} °C, plafond {cap:g} °C"),
        "Ratio_GDD": I(ratio, "-", "power", periode=p, note=label),
        "ET0_total_mm": I(et0.sum(), "mm", "power", periode=p),
        "ETc_total_mm": I(ix.etc(et0, crop["kc"]).sum(), "mm", "power", periode=p,
                          note=f"Kc={crop['kc']}"),
        "CWB": I(ix.cwb(w["PRECTOTCORR"], et0), "mm", "power", periode=p),
        "CWB_culture": I(ix.cwb(w["PRECTOTCORR"], et0, crop["kc"]), "mm", "power", periode=p),
        "Frost_Days": I(ix.frost_days(w["T2M_MIN"]), "jours", "power", periode=p),
        "HSD35": I(ix.heat_stress_days(w["T2M_MAX"], 35), "jours", "power", periode=p),
        "HSD30": I(ix.heat_stress_days(w["T2M_MAX"], 30), "jours", "power", periode=p),
        "Last_Spring_Frost": I(lsf, "jour de l'année", "power", periode=(f"{yr}-01-01", end_p),
                               note=None if lsf is not None else "aucun gel détecté"),
        "VPD_mean_kPa": I(ix.vpd(w["T2M_MAX"], w["T2M_MIN"], rh=w["RH2M"]).mean(), "kPa",
                          "power", periode=p),
    }



def _resume_statut_produit(status_df, dates_attendues):
    """Résume les statuts de publication sur une période attendue."""
    if status_df is None or status_df.empty:
        return "unknown"

    dates_attendues = pd.DatetimeIndex(dates_attendues)
    if len(dates_attendues) == 0:
        return "unknown"

    statuts = status_df["status"].reindex(dates_attendues)
    valeurs = set(statuts.dropna().tolist())

    # Une date absente du tableau de statuts signifie couverture incomplète.
    couverture_incomplete = statuts.isna().any()

    if not valeurs:
        return "unknown"

    if valeurs == {"no_data"}:
        return "no_data"

    if "unknown" in valeurs:
        return "unknown"

    if couverture_incomplete:
        return "incomplete"

    if "no_data" in valeurs:
        return "incomplete"

    if valeurs == {"permanent"}:
        return "permanent"

    if valeurs == {"provisional"}:
        return "provisional"

    if valeurs <= {"permanent", "provisional", "mixed"}:
        return "mixed"

    return "unknown"


def _bloc_gpm(ctx, nom, f):
    """Exécute une partie du bloc GPM ; l'échec est enregistré, sans détruire les autres parties."""
    try:
        return f()
    except Exception as e:                                   # noqa: BLE001 - erreur enregistrée
        ctx["erreurs"][f"gpm.{nom}"] = f"{type(e).__name__}: {e}"
        return None


def _gpm_journalier(ctx, out) -> None:
    lat, lon, start = ctx["lat"], ctx["lon"], ctx["start"]

    # `last_available` = date de la DERNIÈRE image (incluse) ; end est exclu -> +1 jour.
    last_day = pd.Timestamp(cn.last_available(cn.IMERG_HH)).normalize()
    end_g = min(pd.Timestamp(ctx["end"]), last_day + pd.Timedelta(days=1))
    if end_g <= pd.Timestamp(start):
        raise RuntimeError("Aucune donnée GPM journalière disponible sur la période.")
    end_g_str = end_g.strftime("%Y-%m-%d")

    gd = cn.fetch_gpm_daily(lat, lon, start, end_g_str)["precip_mm"]

    # Le dernier jour publié est souvent EN COURS (ex. 8 images sur 48) : il vaut NaN.
    # On l'exclut de la période au lieu de rendre NaN tous les indices de la saison.
    if len(gd) and pd.isna(gd.iloc[-1]) and gd.index[-1] >= last_day:
        gd = gd.iloc[:-1]
        end_g = last_day
        end_g_str = end_g.strftime("%Y-%m-%d")
        ctx["avertissements"].append(
            f"GPM : le dernier jour publié ({last_day:%Y-%m-%d}) est incomplet (< 48 images) : "
            "exclu de la période.")
    if len(gd) == 0 or end_g <= pd.Timestamp(start):
        raise RuntimeError("Aucune journée GPM complète disponible sur la période.")

    p = (start, end_g_str)
    ctx["periodes"]["gpm"] = p
    ctx["gd"] = gd

    # Statuts de publication des images journalières (échec -> statut inconnu, indices conservés).
    daily_dates = pd.date_range(start=start, end=end_g_str, freq="D", inclusive="left")
    daily_status = _bloc_gpm(ctx, "statut_journalier",
                             lambda: cn.fetch_gpm_daily_status(start, end_g_str))
    statut_daily = (_resume_statut_produit(daily_status, daily_dates)
                    if daily_status is not None else "unknown")

    # Les journées NaN (< 48 images) rendent les indices indisponibles ; elles ne sont JAMAIS
    # comptées comme sèches.
    nb_jours_incomplets = int(gd.isna().sum())
    note_daily = (f"Publication GPM : {statut_daily}. "
                  f"Jours sans cumul journalier valide : {nb_jours_incomplets}/{len(gd)}."
                  + (" Indice indisponible (série incomplète)." if nb_jours_incomplets else ""))
    if nb_jours_incomplets:
        dates_nan = ", ".join(d.strftime("%Y-%m-%d") for d in gd.index[gd.isna()][:5])
        ctx["avertissements"].append(
            f"GPM : {nb_jours_incomplets} journée(s) incomplète(s) dans la période "
            f"({dates_nan}{'...' if nb_jours_incomplets > 5 else ''}) : CDD, SDII, R20mm et Rx1day "
            "non calculés (aucune journée manquante n'est remplacée ni comptée comme sèche).")

    for nom, fn, unite in [("CDD", ix.cdd, "jours"), ("SDII", ix.sdii, "mm/jour de pluie"),
                           ("R20mm", ix.r20mm, "jours"), ("Rx1day", ix.rx1day, "mm")]:
        out[nom] = I(fn(gd), unite, "gpm", periode=p, note=note_daily, statut_produit=statut_daily)


def _gpm_mensuel(ctx, out) -> None:
    lat, lon, start = ctx["lat"], ctx["lon"], ctx["start"]

    # Dernier mois publié (date = 1er du mois) ; on récupère tout l'historique disponible
    # (clé de cache indépendante de la période demandée), puis on coupe à la période.
    last_m = pd.Timestamp(cn.last_available(cn.IMERG_MONTHLY)).to_period("M").to_timestamp()
    end_fetch = (last_m + pd.offsets.MonthBegin(1)).strftime("%Y-%m-%d")
    gm = cn.fetch_gpm_monthly(lat, lon, end=end_fetch)

    # Uniquement les mois ENTIERS contenus dans [.., end[ : le SPI/PCI ne dépasse pas la période.
    fin = pd.Timestamp(ctx["end"])
    gm = gm[(gm.index + pd.offsets.MonthBegin(1)) <= fin]
    if len(gm) == 0:
        raise RuntimeError("Aucun mois GPM complet disponible avant la fin de période.")
    ctx["periodes"]["gpm_mensuel"] = (
        gm.index.min().strftime("%Y-%m-%d"),
        (gm.index.max() + pd.offsets.MonthBegin(1)).strftime("%Y-%m-%d"))

    monthly_status = _bloc_gpm(ctx, "statut_mensuel", lambda: cn.fetch_gpm_monthly_status(
        start=gm.index.min().strftime("%Y-%m-%d"),
        end=(gm.index.max() + pd.offsets.MonthBegin(1)).strftime("%Y-%m-%d")))

    for k in (3, 12):
        spi = ix.spi(gm, k).dropna()
        if len(spi):
            last_date = spi.index[-1]
            expected_months = pd.date_range(last_date - pd.DateOffset(months=k - 1),
                                            last_date, freq="MS")      # les k mois du cumul
            statut_spi = (_resume_statut_produit(monthly_status, expected_months)
                          if monthly_status is not None else "unknown")
            out[f"SPI{k}_last"] = I(
                spi.iloc[-1], "-", "gpm", periode=(last_date.strftime("%Y-%m"),),
                note=f"Dernier mois calculable. Publication des {k} mois du cumul : {statut_spi}.",
                statut_produit=statut_spi)
        else:
            out[f"SPI{k}_last"] = I(None, "-", "gpm", note="Historique insuffisant.",
                                    statut_produit="unknown")

    # PCI : uniquement une année civile complète de 12 mois valides.
    full = [year for year, group in gm.groupby(gm.index.year)
            if len(group) == 12 and group.notna().all()]
    if full:
        year = max(full)
        year_months = pd.date_range(f"{year}-01-01", f"{year}-12-01", freq="MS")
        statut_pci = (_resume_statut_produit(monthly_status, year_months)
                      if monthly_status is not None else "unknown")
        out[f"PCI_{year}"] = I(ix.pci(gm[gm.index.year == year]), "-", "gpm",
                               periode=(str(year),),
                               note=f"Année complète. Publication mensuelle : {statut_pci}.",
                               statut_produit=statut_pci)


def _gpm(ctx) -> dict:
    """GPM IMERG V07. Les parties journalière et mensuelle sont indépendantes : l'échec de
    l'une est enregistré dans ctx['erreurs'] (clé `gpm.journalier` / `gpm.mensuel`) sans
    supprimer les résultats de l'autre. Si les deux échouent, le bloc lève une erreur."""
    out: dict = {}
    n_err0 = len(ctx["erreurs"])
    _bloc_gpm(ctx, "journalier", lambda: _gpm_journalier(ctx, out))
    _bloc_gpm(ctx, "mensuel", lambda: _gpm_mensuel(ctx, out))
    if not out:
        raise RuntimeError("aucun indice GPM calculé : "
                           + "; ".join(f"{k}: {v}" for k, v in list(ctx["erreurs"].items())[n_err0:]))
    return out


def _smap(ctx) -> dict:
    if "fc" not in ctx:
        raise RuntimeError("propriétés du sol indisponibles (nécessaires à RSM / SMD)")
    lat, lon, crop, start = ctx["lat"], ctx["lon"], ctx["crop"], ctx["start"]
    end_s = _clip_end(ctx, "smap", cn.SMAP_ID)
    p = (start, end_s)
    sm = cn.fetch_smap(lat, lon, start, end_s)
    fc, pwp = ctx["fc"], ctx["pwp"]

    r = ix.rsm(sm["sm_rootzone"], fc, pwp).replace([np.inf, -np.inf], np.nan).dropna()
    out = {
        "RSM_mean": I(r.mean(), "-", "smap", periode=p),
        "RSM_class_last": I(ix.rsm_class(r.iloc[-1]) if len(r) else None, "classe", "smap",
                            periode=p),
        "RSM_hors_plage_pct": I(100 * ((r < 0) | (r > 1)).mean() if len(r) else None, "%", "smap",
                                periode=p,
                                note="part des jours où RSM sort de [0,1] : incohérence possible "
                                     "entre SMAP (modèle) et FC/PWP (pédotransfert)"),
        "SMAP_rootzone_wetness_mean": I(sm["sm_rootzone_wetness"].mean(), "0-1", "smap", periode=p,
                                        note="indicateur propre à SMAP, pour vérification croisée"),
    }
    smd = ix.smd(fc, sm["sm_rootzone"], crop["zr_mm"]).dropna()
    out["SMD_last_mm"] = I(smd.iloc[-1] if len(smd) else None, "mm", "smap", periode=p)
    out["Jours_praticables"] = I(
        ix.jours_praticables(sm["sm_surface"], sm["surface_temp"], ctx["th_sat"],
                             crop["seuil_praticable"], start, end_s),
        "jours", "smap", periode=p, note=f"seuil de saturation {crop['seuil_praticable']}")
    gd = ctx.get("gd")
    if gd is not None:
        dd = ix.drydown(sm["sm_surface"], gd)
        out["mean_drydown_rate"] = I(dd["mean_drydown_rate"], "m3/m3/jour", "smap", periode=p)
        out["drydown_timescale_tau"] = I(dd["drydown_timescale_tau"], "jours", "smap", periode=p)
        out["drydown_n_events"] = I(dd["n_events"], "épisodes", "smap", periode=p)
    else:
        ctx["avertissements"].append("Dry-down non calculé : pluie GPM indisponible.")
    return out


def _modis(ctx) -> dict:
    lat, lon, start, end = ctx["lat"], ctx["lon"], ctx["start"], ctx["end"]
    p = (start, end)
    out = {}

    def part(nom, f):
        try:
            out.update(f())
        except Exception as e:
            ctx["erreurs"][f"modis.{nom}"] = f"{type(e).__name__}: {e}"

    def refl():
        r = _src(ctx, "modis_refl", lambda: cn.fetch_modis_reflectance(lat, lon, start, end))
        nd = ix.ndvi(r.nir, r.red).replace([np.inf, -np.inf], np.nan)
        return {
            "NDVI_mean": I(nd.mean(), "-", "modis_refl", periode=p),
            "NDVI_sol_nu_pct": I(100 * (nd.dropna() < 0.2).mean() if nd.notna().any() else None,
                                 "% des composites 8 j", "modis_refl", periode=p,
                                 note="NDVI < 0.2 = sol nu (seuil du PDF)"),
            "EVI_mean": I(ix.evi(r.nir, r.red, r.blue).mean(), "-", "modis_refl", periode=p),
            "NDWI_mean": I(ix.ndwi(r.nir, r.swir).mean(), "-", "modis_refl", periode=p),
        }

    def vci():
        h = _src(ctx, "modis_vi_hist", lambda: cn.fetch_modis_vi(lat, lon, "2000-02-18", end),
                 decouper=False)["NDVI"].dropna()
        v = ix.vci(h).dropna()
        vs = _between(v, start, end)
        return {
            "VCI_last": I(v.iloc[-1] if len(v) else None, "%", "modis_vi",
                          periode=(v.index[-1].strftime("%Y-%m-%d"),) if len(v) else None),
            "VCI_season_mean": I(vs.mean() if len(vs) else None, "%", "modis_vi", periode=p),
        }

    def tvdi():
        lst = _src(ctx, "modis_lst", lambda: cn.fetch_modis_lst(lat, lon, start, end))
        b = _src(ctx, "modis_lst_bounds", lambda: cn.fetch_modis_lst_bounds(lat, lon, start, end))
        t = ix.tvdi(lst["LST_Day_1km"], b.lst_min, b.lst_max).replace([np.inf, -np.inf], np.nan)
        return {"TVDI_mean": I(t.mean(), "0-1", "modis_lst", periode=p,
                               note="approximation : LST_min/max = percentiles 5/95 à 10 km")}

    def esi():
        e = _src(ctx, "modis_et", lambda: cn.fetch_modis_et(lat, lon, start, end))
        e = e.assign(PET=e["PET"].where(e["PET"] > 0))
        return {"ESI_mean": I(ix.esi(e["ET"], e["PET"]).mean(), "0-1", "modis_et", periode=p)}

    for nom, f in [("reflectance", refl), ("vci", vci), ("tvdi", tvdi), ("esi", esi)]:
        part(nom, f)
    if not out:
        raise RuntimeError("aucun indice MODIS calculé")
    return out


def _srtm(ctx) -> dict:
    lat, lon, d = ctx["lat"], ctx["lon"], ctx["donnees"]
    zone = d.get("dem") is not None and d.get("dem_mask") is not None
    dem = d["dem"] if zone else cn.fetch_dem_patch(lat, lon)
    upa = d.get("upa")
    if upa is None:
        try:
            upa = cn.fetch_upstream_area_km2(lat, lon)
        except Exception as e:
            ctx["erreurs"]["srtm.upa"] = f"{type(e).__name__}: {e}"
    if zone:
        t = ix.terrain_indices_zone(dem, lat, d["dem_mask"], upa)
        note = f"moyenne sur {t.pop('n_pixels_zone')} pixel(s) SRTM de la parcelle"
    else:
        t = ix.terrain_indices(dem, lat, upa)
        note = "pixel central (pas de polygone)"
    unites = {"elevation_m": "m", "slope_pct": "%", "slope_deg": "°", "aspect_deg": "°",
              "northness": "-", "eastness": "-", "TPI": "m", "TRI": "m",
              "K_prof": "1/m", "K_plan": "1/m", "TWI": "-"}
    out = {k: I(v, unites.get(k, "-"), "merit" if k == "TWI" else "srtm", note=note)
           for k, v in t.items()}
    if "TWI" in out:
        out["TWI"]["note"] = "pente SRTM 30 m + aire drainée MERIT 90 m : approximation"
    return out


# --------------------------------------------------------------------------- #
# Fonction principale
# --------------------------------------------------------------------------- #
def get_indicateurs(parcelle: dict, culture="blé", start: str | None = None,
                    end: str | None = None, donnees: dict | None = None) -> dict:
    """Calcule tous les indices pour une parcelle. `culture` : nom du catalogue ou dict.
    Sans start/end : dernière saison complète de la culture."""
    crop = _resoudre_culture(culture)
    crop_nom = crop.get("nom", "personnalisée")
    donnees = donnees or {}
    if not (start and end):
        start, end = donnees.get("periode") or _saison_par_defaut(crop, dt.date.today())
    if start >= end:
        raise ValueError(f"Période invalide : start ({start}) doit précéder end ({end}, exclu).")
    if donnees.get("periode") and (start < donnees["periode"][0] or end > donnees["periode"][1]):
        raise ValueError(f"Période demandée {start}→{end} hors de celle des données zonales "
                         f"{donnees['periode'][0]}→{donnees['periode'][1]} : relance "
                         "get_donnees_zonales avec la même période.")
    if "centroide" in donnees:
        lat0, lon0 = donnees["centroide"]
    elif parcelle.get("lat") is not None and parcelle.get("lon") is not None:
        lat0, lon0 = parcelle["lat"], parcelle["lon"]
    else:
        raise ValueError("parcelle sans lat/lon et sans donnees['centroide']")
    ha = parcelle.get("surface_ha") or donnees.get("surface_ha")

    ctx = {"lat": round(float(lat0), 4), "lon": round(float(lon0), 4),
           "parcelle": parcelle, "crop": crop, "start": start, "end": end, "donnees": donnees,
           "periodes": {}, "erreurs": {}, "avertissements": list(donnees.get("avertissements", []))}

    blocs = {}
    # l'ordre compte : sol et gpm alimentent smap
    for nom, fn in [("sol", _sol), ("power", _power), ("gpm", _gpm),
                    ("smap", _smap), ("modis", _modis), ("srtm", _srtm)]:
        try:
            blocs[nom] = fn(ctx)
        except Exception as e:
            ctx["erreurs"][nom] = f"{type(e).__name__}: {e}"

    # --- avertissements -------------------------------------------------- #
    cote_m = math.sqrt(ha * 10_000) if ha else None
    ref = cote_m or 1000.0
    vus = set()
    for bloc in blocs.values():
        for ind in bloc.values():
            src, res = ind["source"], ind["resolution_m"]
            if res > ref and src not in vus:
                vus.add(src)
                cible = f"parcelle d'environ {cote_m:.0f} m de côté" if cote_m else "parcelle"
                ctx["avertissements"].append(
                    f"{src} : résolution ≈ {res / 1000:.2g} km, plus grossière que la {cible}. "
                    "Valeur représentative de la zone, pas de la parcelle.")
    if "estimée" in ctx.get("statut_sol", ""):
        ctx["avertissements"].append(
            "Propriétés du sol estimées par SoilGrids (250 m) : fournir une analyse de laboratoire "
            "(parcelle['sol_mesure']) pour améliorer la fiabilité.")
    for src, (d0, d1) in ctx["periodes"].items():
        if d1 < end:
            ctx["avertissements"].append(
                f"{src} : données disponibles seulement jusqu'au {d1} (période demandée jusqu'au {end}).")
    for nom, msg in ctx["erreurs"].items():
        ctx["avertissements"].append(f"Bloc « {nom} » indisponible : {msg}")
    ctx["avertissements"].append(f"Paramètres de culture : {crop.get('source', 'non documentés')}.")
    if crop.get("dates_derivees"):
        ctx["avertissements"].append(
            "Fenêtre de semis/récolte dérivée de `saison` + `duree_cycle` (pas de dates en base) : "
            "ajoute semis_mois, semis_jour, recolte_mois, recolte_jour à la table `culture` pour la fixer.")
    if crop.get("seuil_praticable_defaut"):
        ctx["avertissements"].append(
            f"seuil_praticable absent de la table : valeur par défaut {crop['seuil_praticable']} utilisée.")

    return {
        "parcelle": {"lat": ctx["lat"], "lon": ctx["lon"], "surface_ha": ha,
                     "donnees_zonales": bool(donnees)},
        "culture": {"nom": crop_nom, **{k: v for k, v in crop.items()
                                       if k not in ("semis", "recolte")}},
        "periode": {"start": start, "end": end, "convention": "start inclus, end exclu"},
        "statut_sol": ctx.get("statut_sol"),
        "indicateurs": blocs,
        "avertissements": ctx["avertissements"],
        "erreurs": ctx["erreurs"],
        "meta_zonal": donnees.get("meta"),
    }
