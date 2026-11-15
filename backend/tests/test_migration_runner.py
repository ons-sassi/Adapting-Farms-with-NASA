import pytest

from scripts.migrate import MigrationError, migration_files, split_sql_statements


def test_all_numbered_migrations_split_into_complete_statements():
    files = migration_files()

    assert len(files) == 9
    for path in files:
        statements = split_sql_statements(path.read_text(encoding="utf-8"))
        assert statements
        assert all(statement.strip() for statement in statements)

    snapshot_statements = split_sql_statements(files[4].read_text(encoding="utf-8"))
    assert sum("CREATE TRIGGER" in statement for statement in snapshot_statements) == 2


def test_incomplete_sql_statement_is_rejected():
    with pytest.raises(MigrationError, match="instruction incomplète"):
        split_sql_statements("CREATE TABLE example (id INT)")
