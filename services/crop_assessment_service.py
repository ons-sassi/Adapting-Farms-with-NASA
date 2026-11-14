"""Évaluation d'une culture sur une parcelle : calendrier, indicateurs par saison, contraintes et risques."""
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import mean

from models import Crop, CropCalendar, SoilProfile
from services import agro_indicators as ai
from services.climate_service import ClimateSeries

PROTECTED_CULTIVATION_WORDS = ("serre", "tunnel", "abri")
HEAT_STRESS_THRESHOLD = 35.0  # °C, document des indices (HSD35)
FROST_THRESHOLD = 0.0


@dataclass
class SeasonResult:
    sowing: date
    harvest: date
    gdd: float | None
    ratio_gdd: float | None
    etc_mm: float | None
    rain_mm: float
    cwb_mm: float | None
    irrigation_need_mm: float | None
    frost_days: int
    heat_days: int


@dataclass
class CropAssessment:
    crop: Crop
    calendar: CropCalendar | None
    calendar_in_parcel_zone: bool
    seasons: list[SeasonResult] = field(default_factory=list)
    score_ph: float | None = None
    awc_mm: float | None = None
    rsm: float | None = None
    smd_mm: float | None = None
    excluded_reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)

    @property
    def eligible(self) -> bool:
        return not self.excluded_reasons

    def _avg(self, attr: str) -> float | None:
        values = [getattr(s, attr) for s in self.seasons if getattr(s, attr) is not None]
        return round(mean(values), 2) if values else None

    @property
    def summary(self) -> dict:
        ratio = self._avg("ratio_gdd")
        return {
            "eco_port_code": self.crop.eco_port_code,
            "name": self.crop.display_name,
            "scientific_name": self.crop.scientific_name,
            "family": self.crop.family,
            "n_fixer": self.crop.n_fixer,
            "level": self.crop.level,
            "calendar": None if not self.calendar else {
                "zone": self.calendar.zone_name, "usage": self.calendar.usage,
                "in_parcel_zone": self.calendar_in_parcel_zone,
                "sowing": f"{self.calendar.sow_start_day:02d}/{self.calendar.sow_start_month:02d} → {self.calendar.sow_end_day:02d}/{self.calendar.sow_end_month:02d}",
                "harvest": f"{self.calendar.harvest_start_day:02d}/{self.calendar.harvest_start_month:02d} → {self.calendar.harvest_end_day:02d}/{self.calendar.harvest_end_month:02d}",
            },
            "seasons_analysed": len(self.seasons),
            "indicators": {
                "gdd": self._avg("gdd"), "ratio_gdd": ratio,
                "ratio_gdd_class": ai.ratio_gdd_class(ratio) if ratio is not None else None,
                "etc_mm": self._avg("etc_mm"), "rain_mm": self._avg("rain_mm"), "cwb_mm": self._avg("cwb_mm"),
                "irrigation_need_mm": self._avg("irrigation_need_mm"),
                "frost_days": self._avg("frost_days"), "heat_days": self._avg("heat_days"),
                "score_ph": None if self.score_ph is None else round(self.score_ph, 2),
                "awc_mm": None if self.awc_mm is None else round(self.awc_mm, 1),
                "rsm": None if self.rsm is None else round(self.rsm, 2),
                "smd_mm": None if self.smd_mm is None else round(self.smd_mm, 1),
            },
            "eligible": self.eligible,
            "excluded_reasons": self.excluded_reasons,
            "risks": self.risks,
            "data_gaps": self.data_gaps,
        }


def _midpoint(start: date, end: date) -> date:
    return start + (end - start) / 2


def _window(year: int, m1: int, d1: int, m2: int, d2: int) -> tuple[date, date]:
    start = date(year, m1, min(d1, 28 if m1 == 2 else d1))
    end_year = year if (m2, d2) >= (m1, d1) else year + 1
    end = date(end_year, m2, min(d2, 28 if m2 == 2 else d2))
    return start, end


def season_dates(calendar: CropCalendar, sowing_year: int) -> tuple[date, date]:
    """Semis au milieu de la fenêtre FAO, récolte au milieu de la fenêtre de récolte suivante."""
    s_start, s_end = _window(sowing_year, calendar.sow_start_month, calendar.sow_start_day,
                             calendar.sow_end_month, calendar.sow_end_day)
    sowing = _midpoint(s_start, s_end)
    h_year = sowing.year
    h_start, h_end = _window(h_year, calendar.harvest_start_month, calendar.harvest_start_day,
                             calendar.harvest_end_month, calendar.harvest_end_day)
    while _midpoint(h_start, h_end) <= sowing:
        h_year += 1
        h_start, h_end = _window(h_year, calendar.harvest_start_month, calendar.harvest_start_day,
                                 calendar.harvest_end_month, calendar.harvest_end_day)
    return sowing, _midpoint(h_start, h_end)


def choose_calendar(crop: Crop, zone_id: str | None) -> tuple[CropCalendar | None, bool]:
    open_field = [c for c in crop.calendars if not any(w in (c.usage or "").lower() for w in PROTECTED_CULTIVATION_WORDS)]
    if not open_field:
        return None, False
    in_zone = [c for c in open_field if zone_id and c.zone_id == zone_id]
    return (in_zone[0], True) if in_zone else (open_field[0], False)


def _season(crop: Crop, climate: ClimateSeries, sowing: date, harvest: date) -> SeasonResult | None:
    i0, i1 = climate.index_of(sowing), climate.index_of(harvest)
    if i0 is None or i1 is None:
        return None
    idx = range(i0, i1 + 1)
    tmax = [climate.tmax[i] for i in idx]
    tmin = [climate.tmin[i] for i in idx]
    rain = [climate.precip[i] or 0.0 for i in idx]
    if None in tmax or None in tmin:
        return None

    gdd = ratio = None
    if None not in (crop.t_base, crop.t_upper, crop.gdd_maturity):
        gdd = ai.growing_degree_days(tmax, tmin, crop.t_base, crop.t_upper)
        ratio = ai.ratio_gdd(gdd, crop.gdd_maturity)

    etc = cwb = need = None
    stages = (crop.stage_ini_days, crop.stage_dev_days, crop.stage_mid_days, crop.stage_late_days)
    if None not in stages and None not in (crop.kc_ini, crop.kc_mid, crop.kc_end):
        crop_days = min(len(idx), sum(stages))
        etc_daily = [ai.kc_for_day(d, stages, crop.kc_ini, crop.kc_mid, crop.kc_end) * (climate.et0[i0 + d] or 0.0)
                     for d in range(crop_days)]
        etc = sum(etc_daily)
        cwb = sum(rain[d] - etc_daily[d] for d in range(crop_days))
        need = sum(max(0.0, etc_daily[d] - rain[d]) for d in range(crop_days))

    return SeasonResult(
        sowing=sowing, harvest=harvest, gdd=gdd, ratio_gdd=ratio, etc_mm=etc, rain_mm=sum(rain), cwb_mm=cwb,
        irrigation_need_mm=need,
        frost_days=ai.count_days(tmin, lambda t: t < FROST_THRESHOLD),
        heat_days=ai.count_days(tmax, lambda t: t > HEAT_STRESS_THRESHOLD),
    )


def assess_crop(crop: Crop, zone_id: str | None, climate: ClimateSeries | None,
                soil: SoilProfile | None, irrigation: str) -> CropAssessment:
    calendar, in_zone = choose_calendar(crop, zone_id)
    result = CropAssessment(crop=crop, calendar=calendar, calendar_in_parcel_zone=in_zone)

    if not crop.rotation_eligible:
        result.excluded_reasons.append("Données agronomiques insuffisantes dans le catalogue (niveau 2 ou 3).")
    if calendar is None:
        result.excluded_reasons.append("Aucun calendrier FAO de plein champ pour la Tunisie.")
    elif not in_zone:
        result.risks.append(f"Calendrier d'une autre zone ({calendar.zone_name}) : à vérifier localement.")
    if crop.gdd_maturity is None:
        result.data_gaps.append("Pas de GDD requis sourcé : Ratio_GDD non calculable.")

    if calendar is not None and climate is not None:
        first, last = climate.dates[0].year, climate.dates[-1].year
        for year in range(first - 1, last + 1):
            sowing, harvest = season_dates(calendar, year)
            season = _season(crop, climate, sowing, harvest)
            if season:
                result.seasons.append(season)
        if not result.seasons:
            result.data_gaps.append("Aucune saison complète couverte par la série climatique.")
    elif climate is None:
        result.data_gaps.append("Données climatiques indisponibles : GDD, ETc et CWB non calculés.")

    ratio = result._avg("ratio_gdd")
    if ratio is not None and ratio < 1.0:
        result.excluded_reasons.append(f"Chaleur insuffisante pour mûrir (Ratio_GDD moyen {ratio:.2f} < 1).")
    elif ratio is not None and ratio < 1.05:
        result.risks.append(f"Marge thermique faible (Ratio_GDD {ratio:.2f}).")
    heat = result._avg("heat_days")
    if heat and heat >= 5:
        result.risks.append(f"{heat:.0f} jours > 35 °C en moyenne pendant la saison.")
    frost = result._avg("frost_days")
    if frost and frost >= 1:
        result.risks.append(f"{frost:.0f} jour(s) de gel en moyenne pendant la saison.")
    need = result._avg("irrigation_need_mm")
    if need is not None and irrigation == "none" and need > 0:
        result.risks.append(f"Culture pluviale : déficit hydrique estimé de {need:.0f} mm non compensé par l'irrigation.")

    if soil is None:
        result.data_gaps.append("Aucun profil de sol : Score_pH, AWC, RSM et SMD non calculés.")
    else:
        if soil.ph is not None and None not in (crop.ph_min, crop.ph_max, crop.ph_opt):
            result.score_ph = ai.score_ph(soil.ph, crop.ph_min, crop.ph_max, crop.ph_opt)
            if result.score_ph == 0:
                result.excluded_reasons.append(f"pH du sol ({soil.ph}) incompatible (plage {crop.ph_min}–{crop.ph_max}).")
            elif result.score_ph < 1:
                result.risks.append(f"pH du sol ({soil.ph}) hors de la plage {crop.ph_min}–{crop.ph_max}.")
        if None not in (soil.theta_fc, soil.theta_pwp, crop.root_depth_max_m):
            result.awc_mm = ai.available_water_capacity_mm(soil.theta_fc, soil.theta_pwp, crop.root_depth_max_m)
            if soil.sm_rootzone is not None:
                result.rsm = ai.relative_soil_moisture(soil.sm_rootzone, soil.theta_fc, soil.theta_pwp)
                result.smd_mm = ai.soil_moisture_deficit_mm(soil.theta_fc, soil.sm_rootzone, crop.root_depth_max_m)
                if crop.depletion_fraction_p is not None and result.rsm < 1 - crop.depletion_fraction_p:
                    result.risks.append(f"Humidité du sol mesurée sous le seuil de stress (RSM {result.rsm:.2f} < {1 - crop.depletion_fraction_p:.2f}).")
            else:
                result.data_gaps.append("Humidité du sol non mesurée (SMAP non intégré) : RSM et SMD non calculés.")
    return result


def bare_days_between(previous_harvest: date, next_sowing: date) -> int:
    return max(0, (next_sowing - previous_harvest).days)


def shift_to_campaign(calendar: CropCalendar, campaign_year: int) -> tuple[date, date]:
    """Campagne agricole : 1er septembre de `campaign_year` au 31 août suivant."""
    sowing_year = campaign_year if calendar.sow_start_month >= 9 else campaign_year + 1
    sowing, harvest = season_dates(calendar, sowing_year)
    if sowing < date(campaign_year, 9, 1):
        sowing, harvest = sowing + timedelta(days=365), harvest + timedelta(days=365)
    return sowing, harvest
