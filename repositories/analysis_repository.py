from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Analysis, ClimateCache, SavedRotation


def get_climate_cache(session: Session, lat_key: float, lon_key: float, start: str, end: str) -> ClimateCache | None:
    return session.scalar(select(ClimateCache).where(
        ClimateCache.lat_key == lat_key, ClimateCache.lon_key == lon_key,
        ClimateCache.start_date == start, ClimateCache.end_date == end))


def save_climate_cache(session: Session, lat_key: float, lon_key: float, start: str, end: str,
                       payload: dict, elevation: float | None, source: str) -> ClimateCache:
    entry = ClimateCache(lat_key=lat_key, lon_key=lon_key, start_date=start, end_date=end, payload=payload,
                         elevation_m=elevation, source=source, fetched_at=datetime.now(timezone.utc))
    session.add(entry)
    session.commit()
    return entry


def create_analysis(session: Session, **fields) -> Analysis:
    analysis = Analysis(**fields)
    session.add(analysis)
    session.commit()
    return analysis


def get_analysis(session: Session, analysis_id: int) -> Analysis | None:
    return session.get(Analysis, analysis_id)


def list_analyses(session: Session, parcel_id: int | None = None) -> list[Analysis]:
    query = select(Analysis).order_by(Analysis.id.desc())
    if parcel_id is not None:
        query = query.where(Analysis.parcel_id == parcel_id)
    return list(session.scalars(query))


def save_rotation(session: Session, analysis_id: int, name: str, rotation: dict) -> SavedRotation:
    saved = SavedRotation(analysis_id=analysis_id, name=name, rotation=rotation)
    session.add(saved)
    session.commit()
    return saved


def list_saved_rotations(session: Session) -> list[SavedRotation]:
    return list(session.scalars(select(SavedRotation).order_by(SavedRotation.id.desc())))
