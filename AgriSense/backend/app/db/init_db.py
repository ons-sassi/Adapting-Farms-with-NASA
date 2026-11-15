"""Do not create tables from ORM automatically in production.
Use Alembic migrations after mapping the existing MySQL schema.
"""
from app.db.base import Base
from app.db.session import engine


def create_all_for_local_prototype() -> None:
    Base.metadata.create_all(bind=engine)
