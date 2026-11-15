import json
from pathlib import Path

import pytest

from bd.mysql_ingestor import ImportDatabaseError, MySQLIngestor

MANIFEST = {
    "source": "test fixture",
    "source_reference": "https://example.invalid/catalog",
    "collected_at": "2025-01-02T03:04:05Z",
    "method": "test",
    "dataset_version": "1",
    "units": {"water": "mm"},
}
CONTRACT = {
    "allowed_columns": {"id", "crop", "water"},
    "required_columns": {"id", "crop", "water"},
    "key_columns": ("id",),
    "expected_units": {"water": "mm"},
    "numeric_columns": {"water"},
    "integer_columns": ("id",),
}


class FakeCursor:
    def __init__(self, *, has_unique_key=True, fail_insert=False):
        self.has_unique_key = has_unique_key
        self.fail_insert = fail_insert
        self.result = []
        self.rowcount = 0
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, statement, params=None):
        self.statements.append(statement)
        if statement.startswith("SELECT ENGINE"):
            self.result = [("InnoDB",)]
        elif "SELECT COLUMN_NAME, DATA_TYPE" in statement:
            self.result = [("id", "bigint"), ("crop", "varchar"), ("water", "double")]
        elif "SELECT INDEX_NAME, COLUMN_NAME" in statement:
            self.result = [("uq_id", "id", 0, 1)] if self.has_unique_key else []
        elif statement.startswith("INSERT"):
            if self.fail_insert:
                raise RuntimeError("simulated write failure")
            self.rowcount = 1
        return self.rowcount

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        result, self.result = self.result, []
        return result


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def begin(self):
        pass

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _write_csv(tmp_path: Path, contents: str) -> Path:
    path = tmp_path / "crops.csv"
    path.write_text(contents, encoding="utf-8")
    return path


def _ingest(ingestor, path, manifest=MANIFEST):
    return ingestor.ingest(path, "crops", manifest=manifest, **CONTRACT)


def test_ingest_upserts_only_once_and_archives_source(monkeypatch, tmp_path):
    path = _write_csv(tmp_path, "id,crop,water\n1,wheat,18\n1,wheat,18\n")
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    monkeypatch.setattr("bd.mysql_ingestor.DATA_ROOT", tmp_path / "archive")
    monkeypatch.setattr("bd.mysql_ingestor.pymysql.connect", lambda **kwargs: connection)

    result = _ingest(MySQLIngestor({}, "agri"), path)

    assert result["status"] == "committed"
    assert result["rows_total"] == 2
    assert result["rows_inserted"] == 1
    assert result["rows_ignored"] == 1
    assert connection.committed
    assert not connection.rolled_back
    assert any("ON DUPLICATE KEY UPDATE" in statement for statement in cursor.statements)
    assert not any(statement.startswith(("TRUNCATE", "CREATE", "ALTER")) for statement in cursor.statements)
    assert Path(result["raw_file"]).read_text(encoding="utf-8") == path.read_text(encoding="utf-8")
    log = json.loads((tmp_path / "archive" / "import_logs" / f"{result['batch_id']}.json").read_text())
    assert [row["status"] for row in log["row_log"]] == ["inserted", "ignored_exact_duplicate"]


def test_invalid_unit_quarantines_all_rows_without_connecting(monkeypatch, tmp_path):
    path = _write_csv(tmp_path, "id,crop,water\n1,wheat,18\n")
    monkeypatch.setattr("bd.mysql_ingestor.DATA_ROOT", tmp_path / "archive")
    monkeypatch.setattr(
        "bd.mysql_ingestor.pymysql.connect",
        lambda **kwargs: pytest.fail("database must not be accessed for invalid units"),
    )
    manifest = {**MANIFEST, "units": {"water": "degC"}}

    result = _ingest(MySQLIngestor({}, "agri"), path, manifest)

    assert result["status"] == "quarantined"
    assert result["rows_total"] == 1
    assert result["rows_quarantined"] == 1
    quarantine = json.loads(Path(result["quarantine_file"]).read_text(encoding="utf-8"))
    assert "unité attendue: mm" in quarantine["rows"][0]["errors"][0]


def test_duplicate_business_key_with_conflicting_data_is_quarantined(monkeypatch, tmp_path):
    path = _write_csv(tmp_path, "id,crop,water\n1,wheat,18\n1,barley,21\n")
    monkeypatch.setattr("bd.mysql_ingestor.DATA_ROOT", tmp_path / "archive")
    monkeypatch.setattr(
        "bd.mysql_ingestor.pymysql.connect",
        lambda **kwargs: pytest.fail("conflicting keys must be quarantined before database access"),
    )

    result = _ingest(MySQLIngestor({}, "agri"), path)

    assert result["status"] == "quarantined"
    assert result["rows_quarantined"] == 2
    assert result["rows_inserted"] == 0


def test_missing_unique_key_blocks_upsert_without_ddl(monkeypatch, tmp_path):
    path = _write_csv(tmp_path, "id,crop,water\n1,wheat,18\n")
    cursor = FakeCursor(has_unique_key=False)
    connection = FakeConnection(cursor)
    monkeypatch.setattr("bd.mysql_ingestor.DATA_ROOT", tmp_path / "archive")
    monkeypatch.setattr("bd.mysql_ingestor.pymysql.connect", lambda **kwargs: connection)

    result = _ingest(MySQLIngestor({}, "agri"), path)

    assert result["status"] == "quarantined"
    assert result["rows_quarantined"] == 1
    assert not connection.committed
    assert not any(statement.startswith(("CREATE", "ALTER", "TRUNCATE")) for statement in cursor.statements)


def test_database_failure_rolls_back_and_quarantines_candidates(monkeypatch, tmp_path):
    path = _write_csv(tmp_path, "id,crop,water\n1,wheat,18\n")
    cursor = FakeCursor(fail_insert=True)
    connection = FakeConnection(cursor)
    monkeypatch.setattr("bd.mysql_ingestor.DATA_ROOT", tmp_path / "archive")
    monkeypatch.setattr("bd.mysql_ingestor.pymysql.connect", lambda **kwargs: connection)

    with pytest.raises(ImportDatabaseError):
        _ingest(MySQLIngestor({}, "agri"), path)

    assert connection.rolled_back
    assert connection.closed
    log_paths = list((tmp_path / "archive" / "import_logs").glob("*.json"))
    assert len(log_paths) == 1
    log = json.loads(log_paths[0].read_text(encoding="utf-8"))
    assert log["status"] == "failed"
    assert log["rows_inserted"] == 0
    assert log["rows_quarantined"] == 1
    assert log["row_log"][0]["status"] == "quarantined_database_failure"
