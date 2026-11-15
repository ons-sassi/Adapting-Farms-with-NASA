# Migrations SQL

Apply migrations through `python scripts/migrate.py status` and, only after a
verified database backup, `python scripts/migrate.py apply --backup-confirmed`.
Do not execute the files manually: the runner records each migration checksum
and refuses to adopt an existing untracked schema or resume a partial migration.
MySQL DDL is not transactional, so an interrupted migration requires a schema
inspection and explicit recovery before retrying.

The runner does not create a database or database user. An existing database
without a migration ledger must be inspected and baselined manually; applying
the current scripts blindly to it is not supported.

The SQL scripts use the order `001` users, `002` parcel tables, `003` soil,
`004` indicator calculations, `005` immutable rotation snapshots, `006`
rotation import batches, advisor feedback, and market prices. Document each
new migration's purpose, prerequisites, impact, and rollback limitations.
