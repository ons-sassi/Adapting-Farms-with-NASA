"""Séries climatiques journalières d'une parcelle (NASA POWER, avec cache PostgreSQL)."""
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from integrations import nasa_power
from repositories import analysis_repository
from services import agro_indicators as ai
from settings import settings


@dataclass
class ClimateSeries:
    lat: float
    lon: float
    elevation_m: float | None
    dates: list[date]
    tmax: list[float | None]
    tmin: list[float | None]
    precip: list[float | None]
    rh: list[float | None] | None = None
    wind: list[float | None] | None = None
    radiation: list[float | None] | None = None
    source: str = "NASA POWER"
    fetched_at: str | None = None
    et0: list[float | None] = field(default_factory=list)
    et0_method: str = ""

    def index_of(self, day: date) -> int | None:
        offset = (day - self.dates[0]).days
        return offset if 0 <= offset < len(self.dates) else None

    @property
    def period_label(self) -> str:
        return f"{self.dates[0].isoformat()} → {self.dates[-1].isoformat()}"


def grid_key(lat: float, lon: float) -> tuple[float, float]:
    """Cellule POWER (0,5° × 0,625°) : les parcelles voisines partagent le même cache."""
    return round(round(lat / 0.5) * 0.5, 3), round(round(lon / 0.625) * 0.625, 3)


def _build_series(lat: float, lon: float, payload: dict, source: str, fetched_at: str | None) -> ClimateSeries:
    s = payload["series"]
    series = ClimateSeries(
        lat=lat, lon=lon, elevation_m=payload.get("elevation_m"),
        dates=[datetime.strptime(d, "%Y%m%d").date() for d in payload["dates"]],
        tmax=s["T2M_MAX"], tmin=s["T2M_MIN"], precip=s["PRECTOTCORR"],
        rh=s.get("RH2M"), wind=s.get("WS2M"), radiation=s.get("ALLSKY_SFC_SW_DWN"),
        source=source, fetched_at=fetched_at,
    )
    _compute_et0(series)
    return series


def _compute_et0(series: ClimateSeries) -> None:
    full_pm = series.rh is not None and series.wind is not None and series.radiation is not None and series.elevation_m is not None
    values, used_pm = [], 0
    for i, day in enumerate(series.dates):
        tmax, tmin = series.tmax[i], series.tmin[i]
        if tmax is None or tmin is None:
            values.append(None)
            continue
        doy = day.timetuple().tm_yday
        if full_pm and None not in (series.rh[i], series.wind[i], series.radiation[i]):
            values.append(ai.et0_penman_monteith(tmax, tmin, series.rh[i], series.wind[i], series.radiation[i],
                                                 series.lat, doy, series.elevation_m))
            used_pm += 1
        else:
            values.append(ai.et0_hargreaves(tmax, tmin, series.lat, doy))
    series.et0 = values
    series.et0_method = ("Penman-Monteith FAO-56" if used_pm == len(series.dates)
                         else "Hargreaves FAO-56 (éq. 52)" if used_pm == 0 else "Penman-Monteith + Hargreaves (jours incomplets)")


def get_parcel_climate(session: Session, lat: float, lon: float) -> ClimateSeries:
    """Cache d'abord, puis NASA POWER. Lève ExternalSourceError si aucune donnée n'est disponible."""
    lat_key, lon_key = grid_key(lat, lon)
    start, end = f"{settings.climate_start_year}0101", f"{settings.climate_end_year}1231"
    cached = analysis_repository.get_climate_cache(session, lat_key, lon_key, start, end)
    if cached is None:
        cached = _latest_cache_for_cell(session, lat_key, lon_key)
    if cached is not None:
        return _build_series(lat, lon, cached.payload, cached.source, cached.fetched_at.isoformat())
    payload = nasa_power.fetch_daily_point(lat, lon, start, end)
    entry = analysis_repository.save_climate_cache(session, lat_key, lon_key, start, end, payload,
                                                   payload.get("elevation_m"), "NASA POWER (API)")
    return _build_series(lat, lon, payload, entry.source, entry.fetched_at.isoformat())


def _latest_cache_for_cell(session: Session, lat_key: float, lon_key: float):
    from sqlalchemy import select
    from models import ClimateCache
    return session.scalar(select(ClimateCache).where(ClimateCache.lat_key == lat_key, ClimateCache.lon_key == lon_key)
                          .order_by(ClimateCache.fetched_at.desc()))


def import_power_csv(session: Session, path: Path, lat: float, lon: float, elevation_m: float | None,
                     start: str, source_label: str) -> None:
    """Importe un export NASA POWER réel (une ligne nom de paramètre, une ligne de valeurs) dans le cache."""
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    series = {lines[i]: [float(v) for v in lines[i + 1].split(",")] for i in range(0, len(lines), 2)}
    n_days = len(next(iter(series.values())))
    first = datetime.strptime(start, "%Y%m%d").date()
    dates = [(date.fromordinal(first.toordinal() + i)).strftime("%Y%m%d") for i in range(n_days)]
    payload = {"elevation_m": elevation_m, "dates": dates, "series": series}
    lat_key, lon_key = grid_key(lat, lon)
    analysis_repository.save_climate_cache(session, lat_key, lon_key, dates[0], dates[-1], payload, elevation_m, source_label)
