from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from models import Crop, CropCalendar, DataSource

ELIGIBLE_LEVEL_PREFIXES = ("1a", "1b")


def list_crops(session: Session, search: str | None = None, eligible_only: bool = False, limit: int = 100) -> list[Crop]:
    query = select(Crop).order_by(Crop.level, Crop.display_name)
    if eligible_only:
        query = query.where(or_(*[Crop.level.startswith(p) for p in ELIGIBLE_LEVEL_PREFIXES]))
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(Crop.display_name.ilike(pattern), Crop.scientific_name.ilike(pattern),
                                Crop.common_names.ilike(pattern)))
    return list(session.scalars(query.limit(limit)))


def get_crop(session: Session, code: int) -> Crop | None:
    return session.scalar(select(Crop).where(Crop.eco_port_code == code).options(selectinload(Crop.calendars)))


def get_crops(session: Session, codes: list[int]) -> list[Crop]:
    query = select(Crop).where(Crop.eco_port_code.in_(codes)).options(selectinload(Crop.calendars))
    return list(session.scalars(query))


def list_agro_zones(session: Session, country: str = "TN") -> list[tuple[str, str]]:
    query = (select(CropCalendar.zone_id, CropCalendar.zone_name).where(CropCalendar.country == country)
             .distinct().order_by(CropCalendar.zone_id))
    return [(z, n) for z, n in session.execute(query)]


def list_sources(session: Session) -> list[DataSource]:
    return list(session.scalars(select(DataSource)))
