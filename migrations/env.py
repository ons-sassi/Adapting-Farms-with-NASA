from alembic import context
from sqlalchemy import engine_from_config, pool

import models  # noqa: F401  (enregistre toutes les tables)
from models.base import Base
from settings import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # Tables propres à PostGIS (spatial_ref_sys…) : jamais gérées par nos migrations.
    return not (type_ == "table" and reflected and compare_to is None)


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
