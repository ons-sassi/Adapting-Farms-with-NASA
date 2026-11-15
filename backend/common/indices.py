"""
indices.py : calcul des indices du PDF (fonctions pures, sans accès réseau).
Unités : températures °C, pluie mm/j, rayonnement MJ/m2/j, vent m/s, humidité sol m3/m3.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import gamma as gamma_dist, norm

# =========================== NASA POWER =====================================
def gdd(tmax, tmin, tbase, cap=30.0) -> float:
    """Degrés-jours : plafond à `cap` pour Tmax, plancher à Tbase pour Tmin (comme le PDF)."""
    tx = np.minimum(tmax, cap)
    tx = np.maximum(tx, tbase)
    tn = np.maximum(tmin, tbase)
    return float(np.maximum(0, (tx + tn) / 2 - tbase).sum())


def gdd_ratio(gdd_parcelle, gdd_requis):
    r = gdd_parcelle / gdd_requis
    if r < 1.0:
        label = "risque d'échec de maturité"
    elif 1.05 <= r <= 1.30:
        label = "zone optimale"
    elif r > 1.60:
        label = "mûrit trop vite (ou place pour une dérobée)"
    else:
        label = "intermédiaire (non classé dans le PDF)"
    return r, label


def _e0(t):
    return 0.6108 * np.exp(17.27 * t / (t + 237.3))


def et0_fao56(df: pd.DataFrame, lat: float, elevation: float = 0.0, ea_source="rh") -> pd.Series:
    """ET0 Penman-Monteith FAO-56 (mm/j), G = 0. Colonnes : T2M_MAX, T2M_MIN, WS2M,
    ALLSKY_SFC_SW_DWN et RH2M (ea_source='rh') ou T2MDEW (ea_source='dew')."""
    tmax, tmin = df["T2M_MAX"].values, df["T2M_MIN"].values
    tmean = (tmax + tmin) / 2
    u2, rs = df["WS2M"].values, df["ALLSKY_SFC_SW_DWN"].values
    es = (_e0(tmax) + _e0(tmin)) / 2
    ea = _e0(df["T2MDEW"].values) if ea_source == "dew" else es * df["RH2M"].values / 100

    P = 101.3 * ((293 - 0.0065 * elevation) / 293) ** 5.26
    gam = 0.000665 * P
    delta = 4098 * _e0(tmean) / (tmean + 237.3) ** 2

    # Rayonnement extraterrestre Ra (FAO-56 éq. 21-25)
    J = df.index.dayofyear.values
    phi = np.radians(lat)
    dr = 1 + 0.033 * np.cos(2 * np.pi * J / 365)
    dec = 0.409 * np.sin(2 * np.pi * J / 365 - 1.39)
    ws = np.arccos(np.clip(-np.tan(phi) * np.tan(dec), -1, 1))
    ra = (24 * 60 / np.pi) * 0.0820 * dr * (ws * np.sin(phi) * np.sin(dec)
                                              + np.cos(phi) * np.cos(dec) * np.sin(ws))
    rso = (0.75 + 2e-5 * elevation) * ra
    rel = np.clip(rs / np.where(rso > 0, rso, np.nan), 0.3, 1.0)
    rnl = 4.903e-9 * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2 \
        * (0.34 - 0.14 * np.sqrt(ea)) * (1.35 * rel - 0.35)
    rn = 0.77 * rs - rnl

    et0 = (0.408 * delta * rn + gam * 900 / (tmean + 273) * u2 * (es - ea)) \
        / (delta + gam * (1 + 0.34 * u2))
    return pd.Series(np.maximum(et0, 0), index=df.index, name="ET0")


def etc(et0: pd.Series, kc: float) -> pd.Series:
    return kc * et0


def cwb(precip: pd.Series, et0: pd.Series, kc: float | None = None) -> float:
    """Bilan hydrique climatique (mm). Avec kc : bilan cultural."""
    return float((precip - (kc or 1.0) * et0).sum())


def frost_days(tmin) -> int:
    return int((tmin < 0).sum())


def heat_stress_days(tmax, seuil=35.0) -> int:
    return int((tmax > seuil).sum())


def last_spring_frost(tmin: pd.Series, year: int):
    """Dernier jour de l'année (1-180) avec Tmin < 0 °C (hémisphère nord)."""
    s = tmin[(tmin.index.year == year) & (tmin.index.dayofyear <= 180)]
    d = s[s < 0].index.dayofyear
    return int(d.max()) if len(d) else None


def vpd(tmax, tmin, rh=None, tdew=None) -> pd.Series:
    """VPD (kPa) = es - ea ; ea via RH2M ou via T2MDEW."""
    es = (_e0(tmax) + _e0(tmin)) / 2
    ea = _e0(tdew) if tdew is not None else es * rh / 100
    return es - ea

# =========================== GPM ============================================

def _daily_complete(p: pd.Series) -> bool:
    """True si la série est exploitable pour un indice journalier : non vide, sans NaN/inf,
    et (si l'index est temporel) un jour par date, sans trou ni doublon. Un jour NaN n'est
    JAMAIS interprété comme un jour sec."""
    if p is None or len(p) == 0:
        return False
    v = pd.to_numeric(p, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(v).all() or (v < 0).any():
        return False
    if isinstance(p.index, pd.DatetimeIndex):
        if p.index.has_duplicates or not p.index.is_monotonic_increasing:
            return False
        if len(p) > 1 and not (np.diff(p.index.values) == np.timedelta64(1, "D")).all():
            return False
    return True


def cdd(p: pd.Series, seuil=1.0) -> float:
    """Plus longue séquence de jours secs (< seuil mm). NaN si la série est incomplète."""
    if not _daily_complete(p):
        return np.nan

    best = cur = 0
    for dry in (p.values < seuil):
        cur = cur + 1 if dry else 0
        best = max(best, cur)

    return float(best)


def sdii(p: pd.Series, seuil=1.0) -> float:
    """SDII (ETCCDI) : précipitation totale des jours pluvieux (>= seuil mm) / nombre de ces
    jours. NaN si la série est incomplète, et NaN s'il n'y a aucun jour pluvieux (SDII est
    alors indéfini : 0 serait à tort lu comme « pluies d'intensité nulle »)."""
    if not _daily_complete(p):
        return np.nan

    wet = p[p >= seuil]
    return float(wet.mean()) if len(wet) else np.nan


def r20mm(p: pd.Series) -> float:
    """Nombre de jours avec précipitations >= 20 mm. NaN si la série est incomplète."""
    if not _daily_complete(p):
        return np.nan

    return float((p >= 20.0).sum())


def rx1day(p: pd.Series) -> float:
    """Maximum journalier (Rx1day). NaN si la série est incomplète."""
    if not _daily_complete(p):
        return np.nan

    return float(p.max())



def spi(monthly_precip: pd.Series, k=3, min_years=20) -> pd.Series:
    """
    SPI-k (loi Gamma + probabilité de zéro), par mois calendaire.

    Les mois sans précipitations positives ou avec une série constante
    ne permettent pas un ajustement Gamma : leur SPI reste NaN.

    La série est d'abord ramenée à un calendrier mensuel COMPLET (mois manquants = NaN) :
    `rolling(k)` compte des lignes, pas des mois, donc un mois absent de l'index décalerait
    silencieusement les cumuls. Un cumul contenant un mois NaN est NaN. Précipitation
    négative -> ValueError ; valeur infinie traitée comme manquante.
    """
    if k < 1:
        raise ValueError("k doit être >= 1.")
    if not isinstance(monthly_precip.index, pd.DatetimeIndex):
        raise TypeError("spi() attend une série indexée par date (un point par mois).")
    mp = monthly_precip.astype(float).replace([np.inf, -np.inf], np.nan)
    if (mp.dropna() < 0).any():
        raise ValueError("Précipitations mensuelles négatives : SPI non calculable.")
    per = mp.index.to_period("M")
    if per.has_duplicates:
        raise ValueError("Plusieurs valeurs pour un même mois : SPI non calculable.")
    mp.index = per
    if len(mp) == 0:
        return pd.Series(dtype=float, index=pd.DatetimeIndex([]), name=f"SPI{k}")
    mp = mp.sort_index().reindex(pd.period_range(mp.index.min(), mp.index.max(), freq="M"))
    mp.index = mp.index.to_timestamp()

    roll = mp.rolling(k).sum()
    out = pd.Series(np.nan, index=roll.index, name=f"SPI{k}")

    for m in range(1, 13):
        s = roll[roll.index.month == m].dropna()

        if len(s) < min_years:
            continue

        # Probabilité de précipitation nulle.
        q = float((s == 0).mean())
        pos = s[s > 0]

        # Aucun cumul positif : ajustement Gamma impossible.
        if len(pos) < 2:
            continue

        values = pos.to_numpy(dtype=float)

        # Une série constante ne permet pas un ajustement fiable.
        tolerance = 1e-12 * max(1.0, abs(float(values.mean())))
        if np.ptp(values) <= tolerance:
            continue

        try:
            a, loc, scale = gamma_dist.fit(pos, floc=0)

            if not np.isfinite([a, loc, scale]).all():
                continue

            if a <= 0 or scale <= 0:
                continue

            H = q + (1 - q) * gamma_dist.cdf(
                s, a, loc=loc, scale=scale
            )

            if not np.isfinite(H).all():
                continue

            out.loc[s.index] = norm.ppf(
                np.clip(H, 1e-6, 1 - 1e-6)
            )

        except (ValueError, FloatingPointError):
            continue

    return out



def pci(monthly_year: pd.Series) -> float:
    """
    PCI d'Oliver (1980) pour une année complète.

    Entrée :
        12 cumuls mensuels en mm.

    Retour :
        PCI si les 12 mois sont valides et le cumul annuel positif.
        NaN sinon.
    """
    p = monthly_year.values.astype(float)

    # Vérifier la présence des 12 mois
    if len(p) != 12:
        return np.nan

    # Si l'index est temporel : 12 mois calendaires distincts d'UNE seule année
    if isinstance(monthly_year.index, pd.DatetimeIndex):
        if monthly_year.index.year.nunique() != 1 or monthly_year.index.month.nunique() != 12:
            return np.nan

    # Refuser les valeurs manquantes ou infinies
    if not np.isfinite(p).all():
        return np.nan

    # Refuser les précipitations négatives
    if (p < 0).any():
        return np.nan

    total = p.sum()

    # Éviter une division par zéro
    if total <= 0:
        return np.nan

    return float(100 * np.sum(p ** 2) / total ** 2)
# =========================== SoilGrids ======================================
def saxton_rawls(sand_pct, clay_pct, om_pct):
    """Fonctions de pédotransfert Saxton & Rawls (2006) -> (theta_FC, theta_PWP) en m3/m3.
    SoilGrids ne fournit pas FC/PWP : on les estime depuis texture + matière organique."""
    S, C, OM = sand_pct / 100, clay_pct / 100, min(om_pct, 8.0)
    t1500 = -0.024 * S + 0.487 * C + 0.006 * OM + 0.005 * S * OM - 0.013 * C * OM + 0.068 * S * C + 0.031
    pwp = t1500 + (0.14 * t1500 - 0.02)
    t33 = -0.251 * S + 0.195 * C + 0.011 * OM + 0.006 * S * OM - 0.027 * C * OM + 0.452 * S * C + 0.299
    fc = t33 + (1.283 * t33 ** 2 - 0.374 * t33 - 0.015)
    return fc, pwp


def awc(theta_fc, theta_pwp, zr_mm) -> float:
    return (theta_fc - theta_pwp) * zr_mm


def clay_ratio(clay_pct) -> float:
    return clay_pct / 100


def theta_sat(bdod) -> float:
    return 1 - bdod / 2.65


def som_pct(soc_g_kg) -> float:
    return soc_g_kg / 10 * 1.724


def ratio_cn(soc, nitrogen) -> float:
    return soc / nitrogen


def score_ph(ph, ph_min, ph_max, ph_opt=None) -> float:
    if not np.isfinite(ph):          # max(0.0, nan) vaudrait 0.0 : un NaN ne doit pas devenir un score
        return float("nan")
    if ph_min <= ph <= ph_max:
        return 1.0
    ph_opt = ph_opt if ph_opt is not None else (ph_min + ph_max) / 2
    return max(0.0, 1 - abs(ph - ph_opt) / 1.5)

# =========================== SMAP ===========================================
def rsm(sm_rootzone, theta_fc, theta_pwp):
    return (sm_rootzone - theta_pwp) / (theta_fc - theta_pwp)


def rsm_class(x) -> str | None:
    if x is None or not np.isfinite(x):
        return None                  # NaN : pas de classe (et non « intermédiaire »)
    if x <= 0:
        return "stress hydrique critique"
    if 0.40 <= x <= 0.80:
        return "confort hydrique optimal"
    if x > 1.0:
        return "saturation (asphyxie / lessivage N)"
    return "intermédiaire"


def smd(theta_fc, sm_rootzone, zr_mm):
    """Déficit en mm pour revenir à la capacité au champ."""
    return (theta_fc - sm_rootzone) * zr_mm


def saturation_surface(sm_surface, th_sat):
    return sm_surface / th_sat


def jours_praticables(sm_surface: pd.Series, surface_temp_k: pd.Series, th_sat: float,
                      seuil_max: float, debut: str, fin: str) -> int:
    """Jours où la surface est assez ressuyée ET non gelée. `seuil_max` à calibrer
    (ex. 0.8 de la saturation) selon le sol et le matériel."""
    ok = (saturation_surface(sm_surface, th_sat) < seuil_max) & (surface_temp_k > 273.15)
    return int(ok.loc[debut:fin].sum())


def drydown(sm_surface: pd.Series, precip: pd.Series, dt=4, rain_min=5.0, dry_max=0.1) -> dict:
    """Taux d'assèchement sur les épisodes 'pluie significative puis dt jours secs'.
    t0 = jour qui suit la pluie. rate = (sm(t0) - sm(t0+dt)) / dt.
    tau = dt / ln(sm(t0)/sm(t0+dt)) (approximation exponentielle), moyenné."""
    sm, p = sm_surface.values, precip.reindex(sm_surface.index).values
    rates, taus = [], []
    for t in range(len(sm) - dt - 1):
        if p[t] >= rain_min and np.all(p[t + 1: t + 2 + dt] < dry_max):
            s0, s1 = sm[t + 1], sm[t + 1 + dt]
            if np.isfinite(s0) and np.isfinite(s1) and s0 > s1 > 0:
                rates.append((s0 - s1) / dt)
                taus.append(dt / np.log(s0 / s1))
    return {"mean_drydown_rate": float(np.mean(rates)) if rates else np.nan,
            "drydown_timescale_tau": float(np.mean(taus)) if taus else np.nan,
            "n_events": len(rates)}

# =========================== MODIS ==========================================
def ndvi(nir, red):
    return (nir - red) / (nir + red)


def evi(nir, red, blue):
    return 2.5 * (nir - red) / (nir + 6 * red - 7.5 * blue + 1)


def ndwi(nir, swir):
    return (nir - swir) / (nir + swir)


def vci(ndvi_series: pd.Series) -> pd.Series:
    """VCI (%) : min/max de NDVI par composite (même jour de l'année) sur tout l'historique.
    Fournir l'historique depuis 2000 (fetch_modis_vi(..., '2000-02-18', ...))."""
    g = ndvi_series.groupby(ndvi_series.index.dayofyear)
    mn, mx = g.transform("min"), g.transform("max")
    return (ndvi_series - mn) / (mx - mn).replace(0, np.nan) * 100


def tvdi(lst, lst_min, lst_max):
    return np.clip((lst - lst_min) / (lst_max - lst_min), 0, 1)


def esi(et, pet):
    """ESI = 1 - ET/PET (0 = pas de stress, 1 = déficit sévère)."""
    return np.clip(1 - et / pet, 0, 1)

# =========================== SRTM ===========================================
def terrain_indices(dem: np.ndarray, lat: float, upa_km2: float | None = None,
                    radius_m=300.0, res_deg=1 / 3600) -> dict:
    """Indices au pixel central d'un MNT SRTM 30 m (lignes orientées nord -> sud).
    Aspect : direction vers laquelle la pente descend (0° = nord, 180° = sud)."""
    dy = res_deg * 111_320.0
    dx = dy * np.cos(np.radians(lat))
    zy, zx = np.gradient(dem, dy, dx)             # zy = dz / d(ligne, vers le sud)
    p, q = zx, -zy                                # p : dz/d(est) ; q : dz/d(nord)
    r = np.gradient(zx, dx, axis=1)
    t = np.gradient(zy, dy, axis=0)
    s = -np.gradient(zx, dy, axis=0)

    i, j = dem.shape[0] // 2, dem.shape[1] // 2
    p0, q0, r0, t0, s0 = (a[i, j] for a in (p, q, r, t, s))
    g2 = p0 ** 2 + q0 ** 2
    slope = np.sqrt(g2)
    aspect = np.degrees(np.arctan2(-p0, -q0)) % 360 if slope > 1e-6 else np.nan

    if g2 > 1e-10:
        kprof = -(p0**2 * r0 + 2 * p0 * q0 * s0 + q0**2 * t0) / (g2 * np.sqrt((1 + g2) ** 3))
        kplan = -(q0**2 * r0 - 2 * p0 * q0 * s0 + p0**2 * t0) / g2 ** 1.5
    else:
        kprof = kplan = 0.0

    # TPI : altitude centrale - moyenne du disque de rayon R (centre exclu)
    yy, xx = np.indices(dem.shape)
    dist = np.hypot((yy - i) * dy, (xx - j) * dx)
    ring = (dist <= radius_m) & (dist > 0)
    tpi = dem[i, j] - dem[ring].mean()

    nb = dem[i - 1: i + 2, j - 1: j + 2].copy()
    nb[1, 1] = np.nan
    tri = float(np.sqrt(np.nanmean((nb - dem[i, j]) ** 2)))

    out = {"elevation_m": float(dem[i, j]), "slope_pct": float(slope * 100),
           "slope_deg": float(np.degrees(np.arctan(slope))), "aspect_deg": float(aspect),
           "northness": float(np.cos(np.radians(aspect))) if np.isfinite(aspect) else 0.0,
           "eastness": float(np.sin(np.radians(aspect))) if np.isfinite(aspect) else 0.0,
           "TPI": float(tpi), "TRI": tri, "K_prof": float(kprof), "K_plan": float(kplan)}
    if upa_km2:
        a = upa_km2 * 1e6 / 90.0                  # aire spécifique (largeur de cellule MERIT 90 m)
        out["TWI"] = float(np.log(a / max(slope, 1e-3)))   # tan(S) = gradient
    return out


def terrain_indices_zone(dem: np.ndarray, lat: float, mask: np.ndarray,
                         upa_km2: float | None = None, radius_m=300.0,
                         res_deg=1 / 3600) -> dict:
    """Mêmes indices que terrain_indices, mais MOYENNÉS sur les pixels de la parcelle.
    `mask` : tableau booléen de même forme que `dem` (True = pixel dans la parcelle).
    Sans pixel dans le masque (parcelle plus petite qu'un pixel), on retombe sur le pixel central.
    L'aspect est une moyenne circulaire ; northness/eastness sont des moyennes de cos/sin."""
    from scipy.ndimage import convolve

    dy = res_deg * 111_320.0
    dx = dy * np.cos(np.radians(lat))
    zy, zx = np.gradient(dem, dy, dx)
    p, q = zx, -zy
    r = np.gradient(zx, dx, axis=1)
    t = np.gradient(zy, dy, axis=0)
    s = -np.gradient(zx, dy, axis=0)

    mask = np.asarray(mask, dtype=bool)
    if mask.shape != dem.shape or not mask.any():
        mask = np.zeros(dem.shape, dtype=bool)
        mask[dem.shape[0] // 2, dem.shape[1] // 2] = True

    g2 = p ** 2 + q ** 2
    slope = np.sqrt(g2)
    aspect = np.degrees(np.arctan2(-p, -q)) % 360
    with np.errstate(divide="ignore", invalid="ignore"):
        kprof = np.where(g2 > 1e-10, -(p**2 * r + 2 * p * q * s + q**2 * t)
                         / (g2 * np.sqrt((1 + g2) ** 3)), 0.0)
        kplan = np.where(g2 > 1e-10, -(q**2 * r - 2 * p * q * s + p**2 * t) / g2 ** 1.5, 0.0)

    # TPI : altitude - moyenne du disque (centre exclu), par convolution
    ky, kx = int(np.ceil(radius_m / dy)), int(np.ceil(radius_m / dx))
    oy, ox = np.mgrid[-ky:ky + 1, -kx:kx + 1]
    dist = np.hypot(oy * dy, ox * dx)
    ring = ((dist <= radius_m) & (dist > 0)).astype(float)
    tpi = dem - convolve(dem, ring / ring.sum(), mode="nearest")

    # TRI : racine de la moyenne des carrés des écarts aux 8 voisins
    pad = np.pad(dem, 1, mode="edge")
    n, m = dem.shape
    sq = np.zeros_like(dem)
    for a in (-1, 0, 1):
        for b in (-1, 0, 1):
            if a or b:
                sq += (pad[1 + a:1 + a + n, 1 + b:1 + b + m] - dem) ** 2
    tri = np.sqrt(sq / 8)

    valid = mask & (slope > 1e-6)
    if valid.any():
        north, east = np.cos(np.radians(aspect[valid])).mean(), np.sin(np.radians(aspect[valid])).mean()
        aspect_mean = float(np.degrees(np.arctan2(east, north)) % 360)
    else:
        north = east = 0.0
        aspect_mean = float("nan")

    mean_slope = float(slope[mask].mean())
    out = {"elevation_m": float(dem[mask].mean()),
           "slope_pct": mean_slope * 100,
           "slope_deg": float(np.degrees(np.arctan(slope[mask])).mean()),
           "aspect_deg": aspect_mean,
           "northness": float(north), "eastness": float(east),
           "TPI": float(tpi[mask].mean()), "TRI": float(tri[mask].mean()),
           "K_prof": float(kprof[mask].mean()), "K_plan": float(kplan[mask].mean()),
           "n_pixels_zone": int(mask.sum())}
    if upa_km2:
        a = upa_km2 * 1e6 / 90.0
        out["TWI"] = float(np.log(a / max(mean_slope, 1e-3)))
    return out
