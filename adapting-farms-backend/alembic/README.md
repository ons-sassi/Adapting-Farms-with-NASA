# Alembic

Initialize after the existing MySQL schema has been inspected and SQLAlchemy models
have been mapped. For an existing database, configure a baseline/revision strategy
before running `alembic upgrade`; do not blindly create duplicate tables.
