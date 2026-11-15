"""Conservative runner for the repository's numbered MySQL SQL migrations."""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings

MIGRATIONS_DIR = ROOT / "database" / "migrations"
LEDGER = "schema_migrations"
LOCK_NAME = "adapting_farms_schema_migrations"
EXPECTED_OBJECTS = {
    "001_create_users.sql": {"tables": {"users"}, "triggers": set()},
    "002_create_parcelles.sql": {
        "tables": {"parcelles", "parcelle_cultures", "parcelle_constraints"},
        "triggers": set(),
    },
    "003_create_sol.sql": {"tables": {"soil_analyses"}, "triggers": set()},
    "004_create_indicateurs.sql": {
        "tables": {"indicateur_calculations"},
        "triggers": set(),
    },
    "005_create_rotation_data_snapshots.sql": {
        "tables": {"rotation_data_snapshots"},
        "triggers": {
            "trg_rotation_snapshots_no_update",
            "trg_rotation_snapshots_no_delete",
        },
    },
    "006_rotation_finalisation.sql": {
        "tables": {
            "rotation_import_batches",
            "rotation_advisor_feedback",
            "rotation_market_prices",
        },
        "triggers": set(),
    },
}


class MigrationError(RuntimeError):
    pass


def migration_files() -> list[Path]:
    files = sorted(
        path for path in MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql")
        if path.name in EXPECTED_OBJECTS
    )
    expected_names = sorted(EXPECTED_OBJECTS)
    if [path.name for path in files] != expected_names:
        raise MigrationError("La séquence des fichiers SQL est incomplète ou inattendue.")
    return files


def split_sql_statements(script: str) -> list[str]:
    statements: list[str] = []
    delimiter = ";"
    buffer: list[str] = []

    for line in script.splitlines():
        directive = re.fullmatch(r"\s*DELIMITER\s+(\S+)\s*", line, re.IGNORECASE)
        if directive:
            if "".join(buffer).strip():
                raise MigrationError("Directive DELIMITER rencontrée au milieu d'une instruction.")
            delimiter = directive.group(1)
            continue

        buffer.append(line)
        if line.rstrip().endswith(delimiter):
            statement = "\n".join(buffer).rstrip()
            statement = statement[:-len(delimiter)].strip()
            if statement:
                statements.append(statement)
            buffer.clear()

    if "".join(buffer).strip():
        raise MigrationError("Le fichier de migration se termine par une instruction incomplète.")
    return statements


def _connect():
    return pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        charset="utf8mb4",
        connect_timeout=5,
        read_timeout=30,
        autocommit=False,
    )


def _table_names(cursor) -> set[str]:
    cursor.execute(
        "SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s",
        (settings.mysql_database,),
    )
    return {row[0] for row in cursor.fetchall()}


def _trigger_names(cursor) -> set[str]:
    cursor.execute(
        "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s",
        (settings.mysql_database,),
    )
    return {row[0] for row in cursor.fetchall()}


def _ledger_exists(tables: set[str]) -> bool:
    return LEDGER in tables


def _print_status(connection) -> None:
    with connection.cursor() as cursor:
        tables = _table_names(cursor)
        if not _ledger_exists(tables):
            print("migration_ledger=missing; applied_revision=unknown")
            print("existing_tables=" + (",".join(sorted(tables)) or "none"))
            return

        cursor.execute(
            f"SELECT migration_id, checksum, applied_at FROM `{LEDGER}` ORDER BY migration_id"
        )
        history = cursor.fetchall()
        print("migration_ledger=present")
        if not history:
            print("applied_revision=none")
        for migration_id, checksum, applied_at in history:
            print(f"{migration_id} checksum={checksum} applied_at={applied_at}")

        for path in migration_files():
            if path.name in {row[0] for row in history}:
                continue
            expected = EXPECTED_OBJECTS[path.name]
            existing = expected["tables"] & tables
            existing_triggers = expected["triggers"] & _trigger_names(cursor)
            if existing or existing_triggers:
                print(
                    f"{path.name}=untracked_objects:"
                    + ",".join(sorted(existing | existing_triggers))
                )
            else:
                print(f"{path.name}=pending")


def _ensure_clean_baseline(cursor, tables: set[str]) -> None:
    if _ledger_exists(tables):
        return
    existing = tables - {LEDGER}
    if existing:
        raise MigrationError(
            "Base non vide sans journal de migrations; inspecter et établir une baseline "
            "manuelle avant toute application."
        )
    cursor.execute(
        f"""
        CREATE TABLE `{LEDGER}` (
            migration_id VARCHAR(128) NOT NULL PRIMARY KEY,
            checksum CHAR(64) NOT NULL,
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def _load_history(cursor) -> dict[str, str]:
    cursor.execute(f"SELECT migration_id, checksum FROM `{LEDGER}`")
    return {migration_id: checksum for migration_id, checksum in cursor.fetchall()}


def _assert_unapplied_objects_absent(cursor, path: Path) -> None:
    objects = EXPECTED_OBJECTS[path.name]
    tables = _table_names(cursor)
    triggers = _trigger_names(cursor)
    present = (objects["tables"] & tables) | (objects["triggers"] & triggers)
    if present:
        raise MigrationError(
            f"{path.name} n'est pas journalisée mais des objets existent déjà: "
            + ", ".join(sorted(present))
            + ". Vérification manuelle requise; aucune réparation automatique n'a été tentée."
        )


def _apply(connection, backup_confirmed: bool) -> None:
    if not backup_confirmed:
        raise MigrationError(
            "Application refusée : vérifier une sauvegarde exploitable puis fournir "
            "--backup-confirmed."
        )

    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 30)", (LOCK_NAME,))
        if cursor.fetchone()[0] != 1:
            raise MigrationError("Impossible d'obtenir le verrou de migration.")

        try:
            tables = _table_names(cursor)
            _ensure_clean_baseline(cursor, tables)
            connection.commit()
            history = _load_history(cursor)
            files = migration_files()

            for path in files:
                checksum = hashlib.sha256(path.read_bytes()).hexdigest()
                if path.name in history:
                    if history[path.name] != checksum:
                        raise MigrationError(
                            f"Checksum différent pour {path.name}; migration modifiée après application."
                        )
                    print(path.name + "=already_applied")
                    continue

                _assert_unapplied_objects_absent(cursor, path)
                sql = path.read_text(encoding="utf-8")
                for statement in split_sql_statements(sql):
                    cursor.execute(statement)
                connection.commit()

                cursor.execute(
                    f"INSERT INTO `{LEDGER}` (migration_id, checksum) VALUES (%s, %s)",
                    (path.name, checksum),
                )
                connection.commit()
                history[path.name] = checksum
                print(path.name + "=applied")
        finally:
            cursor.execute("SELECT RELEASE_LOCK(%s)", (LOCK_NAME,))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Inspect migration ledger without changing the schema")
    apply_parser = commands.add_parser("apply", help="Apply pending migrations to an empty, backed-up database")
    apply_parser.add_argument(
        "--backup-confirmed",
        action="store_true",
        help="Confirm that a verified database backup exists",
    )
    args = parser.parse_args(argv)

    connection = None
    try:
        connection = _connect()
        if args.command == "status":
            _print_status(connection)
        else:
            _apply(connection, args.backup_confirmed)
    except MigrationError as exc:
        print("migration_error=" + str(exc), file=sys.stderr)
        return 2
    except pymysql.MySQLError as exc:
        code = exc.args[0] if exc.args and isinstance(exc.args[0], int) else "unknown"
        print(f"mysql_error_type={type(exc).__name__} mysql_error_code={code}", file=sys.stderr)
        return 3
    finally:
        if connection is not None:
            connection.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
