"""Indicateurs agronomiques (fonctions pures). Formules : FAO-56 et document des indices de l'équipe."""
import math
from collections.abc import Sequence

SOLAR_CONSTANT = 0.0820  # MJ m-2 min-1


def extraterrestrial_radiation(lat_deg: float, doy: int) -> float:
    """Ra (MJ m-2 jour-1), FAO-56 éq. 21."""
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    delta = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(phi) * math.tan(delta))))
    return (24 * 60 / math.pi) * SOLAR_CONSTANT * dr * (
        ws * math.sin(phi) * math.sin(delta) + math.cos(phi) * math.cos(delta) * math.sin(ws))


def saturation_vapour_pressure(t: float) -> float:
    return 0.6108 * math.exp(17.27 * t / (t + 237.3))


def et0_hargreaves(tmax: float, tmin: float, lat_deg: float, doy: int) -> float:
    """FAO-56 éq. 52 : méthode de repli quand l'humidité, le vent ou le rayonnement manquent."""
    tmean = (tmax + tmin) / 2
    ra_mm = 0.408 * extraterrestrial_radiation(lat_deg, doy)
    return max(0.0, 0.0023 * (tmean + 17.8) * math.sqrt(max(tmax - tmin, 0.0)) * ra_mm)


def et0_penman_monteith(tmax: float, tmin: float, rh_mean: float, u2: float, rs: float,
                        lat_deg: float, doy: int, elevation_m: float) -> float:
    """FAO-56 éq. 6 (pas journalier, G = 0). rs en MJ m-2 jour-1."""
    tmean = (tmax + tmin) / 2
    pressure = 101.3 * ((293 - 0.0065 * elevation_m) / 293) ** 5.26
    gamma = 0.000665 * pressure
    delta = 4098 * saturation_vapour_pressure(tmean) / (tmean + 237.3) ** 2
    es = (saturation_vapour_pressure(tmax) + saturation_vapour_pressure(tmin)) / 2
    ea = es * rh_mean / 100
    ra = extraterrestrial_radiation(lat_deg, doy)
    rso = (0.75 + 2e-5 * elevation_m) * ra
    rns = 0.77 * rs
    sigma = 4.903e-9
    ratio = min(rs / rso, 1.0) if rso > 0 else 0.5
    rnl = sigma * (((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2) * (0.34 - 0.14 * math.sqrt(max(ea, 0))) * (1.35 * ratio - 0.35)
    rn = rns - rnl
    num = 0.408 * delta * rn + gamma * (900 / (tmean + 273)) * u2 * (es - ea)
    return max(0.0, num / (delta + gamma * (1 + 0.34 * u2)))


def growing_degree_days(tmax: Sequence[float], tmin: Sequence[float], t_base: float, t_upper: float) -> float:
    """GDD = Σ max(0, (Tmax* + Tmin*)/2 − Tbase), Tmax* plafonnée à Tupper, Tmin* relevée à Tbase."""
    total = 0.0
    for hi, lo in zip(tmax, tmin):
        hi = min(hi, t_upper)
        lo = max(lo, t_base)
        hi = max(hi, lo)
        total += max(0.0, (hi + lo) / 2 - t_base)
    return total


def kc_for_day(day_index: int, stages: tuple[int, int, int, int], kc_ini: float, kc_mid: float, kc_end: float) -> float:
    """Courbe Kc FAO-56 (fig. 25) : constante, rampe, constante, rampe."""
    l_ini, l_dev, l_mid, l_late = stages
    if day_index < l_ini:
        return kc_ini
    if day_index < l_ini + l_dev:
        return kc_ini + (kc_mid - kc_ini) * (day_index - l_ini + 1) / l_dev
    if day_index < l_ini + l_dev + l_mid:
        return kc_mid
    if day_index < l_ini + l_dev + l_mid + l_late:
        return kc_mid + (kc_end - kc_mid) * (day_index - l_ini - l_dev - l_mid + 1) / l_late
    return kc_end


def ratio_gdd(gdd_parcel: float, gdd_required: float) -> float:
    return gdd_parcel / gdd_required


def ratio_gdd_class(ratio: float) -> str:
    if ratio < 1.0:
        return "risque_echec_maturite"
    if ratio < 1.05:
        return "juste"
    if ratio <= 1.30:
        return "optimal"
    if ratio <= 1.60:
        return "confortable"
    return "maturite_trop_rapide"


def score_ph(ph_soil: float, ph_min: float, ph_max: float, ph_opt: float) -> float:
    """Document des indices : 1 dans [pHmin, pHmax], sinon max(0, 1 − |pH − pHopt| / 1.5)."""
    if ph_min <= ph_soil <= ph_max:
        return 1.0
    return max(0.0, 1 - abs(ph_soil - ph_opt) / 1.5)


def relative_soil_moisture(sm_rootzone: float, theta_fc: float, theta_pwp: float) -> float:
    return (sm_rootzone - theta_pwp) / (theta_fc - theta_pwp)


def soil_moisture_deficit_mm(theta_fc: float, sm_rootzone: float, root_depth_m: float) -> float:
    return max(0.0, (theta_fc - sm_rootzone) * root_depth_m * 1000)


def available_water_capacity_mm(theta_fc: float, theta_pwp: float, root_depth_m: float) -> float:
    return max(0.0, (theta_fc - theta_pwp) * root_depth_m * 1000)


def count_days(values: Sequence[float], predicate) -> int:
    return sum(1 for v in values if predicate(v))
