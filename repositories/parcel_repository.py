import json

from geoalchemy2.functions import ST_Area, ST_AsGeoJSON, ST_Centroid, ST_GeomFromGeoJSON, ST_IsValid, ST_X, ST_Y
from sqlalchemy import cast, func, select
from geoalchemy2 import Geography
from sqlalchemy.orm import Session, selectinload

from models import Parcel, SoilProfile


def _geometry_expr(geojson: dict):
    return func.ST_SetSRID(ST_GeomFromGeoJSON(json.dumps(geojson)), 4326)


def is_valid_geometry(session: Session, geojson: dict) -> bool:
    return bool(session.scalar(select(ST_IsValid(_geometry_expr(geojson)))))


def list_parcels(session: Session) -> list[Parcel]:
    return list(session.scalars(select(Parcel).order_by(Parcel.id.desc())))


def get_parcel(session: Session, parcel_id: int) -> Parcel | None:
    return session.scalar(select(Parcel).where(Parcel.id == parcel_id).options(selectinload(Parcel.soil_profiles)))


def create_parcel(session: Session, data: dict, geojson: dict) -> Parcel:
    parcel = Parcel(**data, geometry=_geometry_expr(geojson))
    session.add(parcel)
    session.commit()
    return get_parcel(session, parcel.id)


def update_parcel(session: Session, parcel: Parcel, data: dict, geojson: dict | None) -> Parcel:
    for key, value in data.items():
        setattr(parcel, key, value)
    if geojson is not None:
        parcel.geometry = _geometry_expr(geojson)
    session.commit()
    return get_parcel(session, parcel.id)


def delete_parcel(session: Session, parcel: Parcel) -> None:
    session.delete(parcel)
    session.commit()


def geometry_info(session: Session, parcel_id: int) -> dict:
    """GeoJSON, surface (ha, calculée sur l'ellipsoïde par PostGIS) et centroïde."""
    geom = select(Parcel.geometry).where(Parcel.id == parcel_id).scalar_subquery()
    row = session.execute(select(
        ST_AsGeoJSON(geom),
        ST_Area(cast(geom, Geography)) / 10000.0,
        ST_Y(ST_Centroid(geom)),
        ST_X(ST_Centroid(geom)),
    )).one()
    return {"geometry": json.loads(row[0]), "area_ha": round(row[1], 3),
            "centroid": {"lat": round(row[2], 6), "lon": round(row[3], 6)}}


def add_soil_profile(session: Session, parcel: Parcel, data: dict) -> SoilProfile:
    profile = SoilProfile(parcel_id=parcel.id, **data)
    session.add(profile)
    session.commit()
    return profile


def latest_soil_profile(parcel: Parcel) -> SoilProfile | None:
    """Une analyse mesurée prime sur une estimation SoilGrids."""
    measured = [p for p in parcel.soil_profiles if p.data_status == "measured"]
    pool = measured or list(parcel.soil_profiles)
    return max(pool, key=lambda p: p.id) if pool else None
