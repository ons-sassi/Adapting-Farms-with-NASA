from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import unicodedata
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pymysql

DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "external_agri"
PROVENANCE_FIELDS = ("source", "source_reference", "collected_at", "method", "dataset_version")
UNIT_ALIASES = {
    "c": "degc",
    "°c": "degc",
    "celsius": "degc",
    "degc": "degc",
    "c-day": "degc_day",
    "°c-day": "degc_day",
    "°c·day": "degc_day",
    "degc_day": "degc_day",
    "mm": "mm",
    "day": "day",
    "days": "day",
    "d": "day",
    "1": "1",
    "dimensionless": "1",
    "ph": "ph",
}


class ImportValidationError(ValueError):
    pass


class ImportDatabaseError(RuntimeError):
    pass


class MySQLIngestor:
    def __init__(self, db_config: dict[str, Any], database: str):
        self.db_config = {**db_config, "charset": "utf8mb4", "autocommit": False}
        self.database = self._clean_name(database)

    @staticmethod
    def _clean_name(name: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", normalized.lower()).strip("_")[:64]
        if not cleaned:
            raise ImportValidationError("Nom de table ou de colonne vide après normalisation.")
        return f"col_{cleaned}"[:64] if cleaned[0].isdigit() else cleaned

    @staticmethod
    def _quote_id(identifier: str) -> str:
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]{0,63}", identifier):
            raise ImportValidationError("Identifiant SQL non autorisé.")
        return f"`{identifier}`"

    @staticmethod
    def _canonical_unit(unit: str) -> str:
        key = " ".join(str(unit).strip().lower().split())
        return UNIT_ALIASES.get(key, key)

    @staticmethod
    def _native_value(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): MySQLIngestor._native_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [MySQLIngestor._native_value(item) for item in value]
        if value is None:
            return value
        if isinstance(value, float) and math.isnan(value):
            return None
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, str):
            return value.strip() or None
        return value

    @staticmethod
    def _canonical_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False, default=str),
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _read_file(filepath: Path) -> tuple[list[dict[str, Any]], list[str]]:
        extension = filepath.suffix.lower()
        try:
            if extension == ".csv":
                text = filepath.read_text(encoding="utf-8-sig")
                if not text.strip():
                    return [], []
                try:
                    dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
                except csv.Error:
                    dialect = csv.excel
                reader = csv.DictReader(io.StringIO(text), dialect=dialect)
                if not reader.fieldnames:
                    raise ImportValidationError("Le CSV doit contenir une ligne d'en-tête.")
                columns = list(reader.fieldnames)
                records = []
                for row in reader:
                    if None in row:
                        raise ImportValidationError("Ligne CSV avec plus de champs que l'en-tête.")
                    records.append(row)
            elif extension in {".json", ".jsonl"}:
                text = filepath.read_text(encoding="utf-8-sig")
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    data = [json.loads(line) for line in text.splitlines() if line.strip()]
                if isinstance(data, dict):
                    data = data.get("records", [data])
                if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
                    raise ImportValidationError("JSON attendu : un objet ou une liste d'objets.")
                records = [MySQLIngestor._flatten_json_record(row) for row in data]
                columns = list(dict.fromkeys(column for row in records for column in row))
            else:
                raise ImportValidationError(f"Format non supporté : {extension or 'sans extension'}.")
        except (UnicodeError, json.JSONDecodeError, csv.Error) as exc:
            raise ImportValidationError(f"Dataset illisible ({type(exc).__name__}).") from exc

        normalized_columns = [MySQLIngestor._clean_name(column) for column in columns]
        if len(normalized_columns) != len(set(normalized_columns)):
            raise ImportValidationError("Plusieurs colonnes deviennent identiques après normalisation.")
        normalized_records = [
            {
                MySQLIngestor._clean_name(column): MySQLIngestor._native_value(value)
                for column, value in row.items()
            }
            for row in records
        ]
        return normalized_records, normalized_columns

    @staticmethod
    def _flatten_json_record(record: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        flattened: dict[str, Any] = {}
        for key, value in record.items():
            column = f"{prefix}_{key}" if prefix else str(key)
            if isinstance(value, dict):
                flattened.update(MySQLIngestor._flatten_json_record(value, column))
            else:
                flattened[column] = value
        return flattened

    @staticmethod
    def _validate_provenance(manifest: dict[str, Any]) -> dict[str, Any]:
        missing = [
            field for field in PROVENANCE_FIELDS
            if not isinstance(manifest.get(field), str) or not manifest[field].strip()
        ]
        if missing:
            raise ImportValidationError("Provenance manquante : " + ", ".join(missing))
        try:
            datetime.fromisoformat(manifest["collected_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ImportValidationError("collected_at doit être une date ISO-8601.") from exc
        units = manifest.get("units")
        if not isinstance(units, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in units.items()):
            raise ImportValidationError("units doit être un objet colonne → unité.")
        return {
            **manifest,
            "units": {
                MySQLIngestor._clean_name(key): MySQLIngestor._canonical_unit(value)
                for key, value in units.items()
            },
            "imported_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _validate_contract(
        columns: list[str],
        allowed_columns: Iterable[str],
        required_columns: Iterable[str],
        key_columns: Iterable[str],
        manifest_units: dict[str, str],
        expected_units: dict[str, str],
    ) -> tuple[set[str], tuple[str, ...]]:
        allowed = {MySQLIngestor._clean_name(column) for column in allowed_columns}
        required = {MySQLIngestor._clean_name(column) for column in required_columns}
        keys = tuple(MySQLIngestor._clean_name(column) for column in key_columns)
        if not keys or len(keys) != len(set(keys)):
            raise ImportValidationError("La clé d'upsert doit contenir au moins une colonne unique.")
        if not required.issubset(allowed) or not set(keys).issubset(required):
            raise ImportValidationError("Le contrat de colonnes ou de clés est incohérent.")

        unknown = set(columns) - allowed
        missing = required - set(columns)
        if unknown or missing:
            details = []
            if unknown:
                details.append("colonnes inconnues: " + ", ".join(sorted(unknown)))
            if missing:
                details.append("colonnes obligatoires absentes: " + ", ".join(sorted(missing)))
            raise ImportValidationError("; ".join(details))

        expected = {
            MySQLIngestor._clean_name(name): MySQLIngestor._canonical_unit(unit)
            for name, unit in expected_units.items()
        }
        for column in set(columns) & set(expected):
            if manifest_units.get(column) != expected[column]:
                raise ImportValidationError(
                    f"Unité absente ou incompatible pour {column}; unité attendue: {expected[column]}."
                )
        return required, keys

    @staticmethod
    def _normalize_record(
        record: dict[str, Any],
        required_columns: set[str],
        numeric_columns: set[str],
        integer_columns: set[str],
        boolean_columns: set[str],
    ) -> tuple[dict[str, Any], list[str]]:
        row = {key: MySQLIngestor._native_value(value) for key, value in record.items()}
        errors = [f"{column}: valeur obligatoire manquante" for column in required_columns if row.get(column) is None]

        for column in numeric_columns:
            value = row.get(column)
            if value is None:
                continue
            try:
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError
                if column in integer_columns:
                    if not number.is_integer():
                        raise ValueError
                    row[column] = int(number)
                else:
                    row[column] = number
            except (TypeError, ValueError):
                errors.append(f"{column}: valeur numérique invalide")

        for column in boolean_columns:
            value = row.get(column)
            if value is None or isinstance(value, bool):
                continue
            normalized = str(value).strip().lower()
            if normalized in {"1", "true", "yes"}:
                row[column] = True
            elif normalized in {"0", "false", "no"}:
                row[column] = False
            else:
                errors.append(f"{column}: booléen invalide")
        return row, errors

    @staticmethod
    def _classify_records(
        records: list[dict[str, Any]],
        required: set[str],
        keys: tuple[str, ...],
        numeric: set[str],
        integers: set[str],
        booleans: set[str],
        first_row_number: int,
    ) -> tuple[list[tuple[int, dict[str, Any], str]], list[dict[str, Any]], list[dict[str, Any]]]:
        groups: dict[tuple[str, ...], list[tuple[int, dict[str, Any], str]]] = {}
        quarantine: list[dict[str, Any]] = []
        row_log: list[dict[str, Any]] = []
        for row_number, raw_record in enumerate(records, start=first_row_number):
            record = {key: MySQLIngestor._native_value(value) for key, value in raw_record.items()}
            row, errors = MySQLIngestor._normalize_record(record, required, numeric, integers, booleans)
            digest = hashlib.sha256(MySQLIngestor._canonical_json(row).encode("utf-8")).hexdigest()
            if errors:
                quarantine.append({"row_number": row_number, "row": row, "errors": errors})
                row_log.append({"row_number": row_number, "sha256": digest, "status": "rejected", "errors": errors})
                continue
            key = tuple(str(row[column]) for column in keys)
            groups.setdefault(key, []).append((row_number, row, digest))

        candidates = []
        for grouped_rows in groups.values():
            digests = {item[2] for item in grouped_rows}
            if len(digests) > 1:
                errors = ["Clé métier dupliquée avec des contenus différents; validation manuelle requise."]
                for row_number, row, digest in grouped_rows:
                    quarantine.append({"row_number": row_number, "row": row, "errors": errors})
                    row_log.append({
                        "row_number": row_number,
                        "sha256": digest,
                        "status": "quarantined_conflicting_key",
                        "errors": errors,
                    })
                continue
            row_number, row, digest = grouped_rows[0]
            candidates.append((row_number, row, digest))
            row_log.append({"row_number": row_number, "sha256": digest, "status": "pending_upsert"})
            for duplicate_number, _, duplicate_digest in grouped_rows[1:]:
                row_log.append({
                    "row_number": duplicate_number,
                    "sha256": duplicate_digest,
                    "status": "ignored_exact_duplicate",
                })
        return candidates, quarantine, row_log

    def _archive_raw(self, filepath: Path) -> tuple[str, str]:
        raw = filepath.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        archive_dir = DATA_ROOT / "raw" / "imports"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"{digest}_{filepath.name}"
        if archive_path.exists():
            if hashlib.sha256(archive_path.read_bytes()).hexdigest() != digest:
                raise OSError("Le fichier brut archivé ne correspond plus à son empreinte.")
        else:
            archive_path.write_bytes(raw)
        return digest, str(archive_path)

    def _validate_target(
        self,
        cursor,
        table: str,
        columns: list[str],
        key_columns: tuple[str, ...],
        numeric_columns: set[str],
    ) -> None:
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
            (self.database, table),
        )
        table_row = cursor.fetchone()
        if table_row is None:
            raise ImportValidationError(
                f"La table {self.database}.{table} n'existe pas; aucune création automatique n'est autorisée."
            )
        if str(table_row[0]).lower() != "innodb":
            raise ImportValidationError("La table cible doit utiliser InnoDB pour garantir la transaction.")

        cursor.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
            """,
            (self.database, table),
        )
        target_columns = {row[0]: row[1].lower() for row in cursor.fetchall()}
        missing = set(columns) - set(target_columns)
        if missing:
            raise ImportValidationError("Colonnes absentes de la table cible: " + ", ".join(sorted(missing)))

        numeric_types = {"tinyint", "smallint", "mediumint", "int", "integer", "bigint", "decimal", "float", "double"}
        nonnumeric_measurements = [
            column for column in columns
            if column in target_columns
            and column in numeric_columns
            and target_columns[column] not in numeric_types
        ]
        if nonnumeric_measurements:
            raise ImportValidationError(
                "Les colonnes numériques attendues ne sont pas numériques dans la table cible: "
                + ", ".join(nonnumeric_measurements)
            )

        cursor.execute(
            """
            SELECT INDEX_NAME, COLUMN_NAME, NON_UNIQUE, SEQ_IN_INDEX
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
            ORDER BY INDEX_NAME, SEQ_IN_INDEX
            """,
            (self.database, table),
        )
        indexes: dict[str, dict[str, Any]] = {}
        for name, column, non_unique, sequence in cursor.fetchall():
            index = indexes.setdefault(name, {"non_unique": non_unique, "columns": []})
            index["columns"].append((sequence, column))

        key = tuple(key_columns)
        matching = [
            name for name, index in indexes.items()
            if index["non_unique"] == 0
            and tuple(column for _, column in index["columns"]) == key
        ]
        if not matching:
            raise ImportValidationError(
                "La clé d'upsert doit correspondre exactement à un index UNIQUE existant; "
                "aucun index n'a été ajouté automatiquement."
            )
        unexpected = [
            name for name, index in indexes.items()
            if index["non_unique"] == 0 and name not in matching
            and not (
                name == "PRIMARY"
                and len(index["columns"]) == 1
                and index["columns"][0][1] not in columns
            )
        ]
        if unexpected:
            raise ImportValidationError(
                "Index UNIQUE additionnels à examiner avant upsert: " + ", ".join(sorted(unexpected))
            )

    def _write_report(
        self,
        report: dict[str, Any],
        quarantine: list[dict[str, Any]],
        row_log: list[dict[str, Any]],
    ) -> None:
        if quarantine:
            path = DATA_ROOT / "quarantine" / f"{report['batch_id']}.json"
            self._write_json(path, {"batch_id": report["batch_id"], "rows": quarantine})
            report["quarantine_file"] = str(path)
        report["rows_quarantined"] = len(quarantine)
        report["row_log"] = row_log
        self._write_json(DATA_ROOT / "import_logs" / f"{report['batch_id']}.json", report)

    def ingest(
        self,
        filepath: str | Path,
        table_name: str,
        *,
        manifest: dict[str, Any],
        allowed_columns: Iterable[str],
        required_columns: Iterable[str],
        key_columns: Iterable[str],
        expected_units: dict[str, str],
        numeric_columns: Iterable[str],
        integer_columns: Iterable[str] = (),
        boolean_columns: Iterable[str] = (),
    ) -> dict[str, Any]:
        """Archive source bytes, validate a declared contract, then transactionally upsert.

        No database, table, column, or index is created or altered. There is no truncate option.
        """
        source_path = Path(filepath)
        if not source_path.is_file():
            raise FileNotFoundError(f"Dataset source introuvable: {source_path}")
        batch_id = str(uuid.uuid4())
        raw_hash, raw_path = self._archive_raw(source_path)
        report: dict[str, Any] = {
            "batch_id": batch_id,
            "status": "preparing",
            "table": f"{self.database}.{self._clean_name(table_name)}",
            "raw_sha256": raw_hash,
            "raw_file": raw_path,
            "provenance": manifest,
            "rows_total": 0,
            "rows_inserted": 0,
            "rows_updated": 0,
            "rows_ignored": 0,
            "rows_rejected": 0,
            "rows_quarantined": 0,
        }
        records: list[dict[str, Any]] = []
        quarantine: list[dict[str, Any]] = []
        row_log: list[dict[str, Any]] = []

        try:
            records, columns = self._read_file(source_path)
            report["rows_total"] = len(records)
            report["columns"] = columns
            clean_manifest = self._validate_provenance(manifest)
            report["provenance"] = clean_manifest
            units = {
                self._clean_name(name): self._canonical_unit(unit)
                for name, unit in clean_manifest["units"].items()
            }
            required, keys = self._validate_contract(
                columns, allowed_columns, required_columns, key_columns, units, expected_units
            )
            numeric = {self._clean_name(column) for column in numeric_columns}
            integers = {self._clean_name(column) for column in integer_columns}
            booleans = {self._clean_name(column) for column in boolean_columns}
            first_row_number = 2 if source_path.suffix.lower() == ".csv" else 1
            candidates, quarantine, row_log = self._classify_records(
                records, required, keys, numeric, integers, booleans, first_row_number
            )
        except ImportValidationError as exc:
            quarantine = [
                {"row_number": index + 1, "row": record, "errors": [str(exc)]}
                for index, record in enumerate(records)
            ]
            report["status"] = "quarantined"
            report["validation_error"] = str(exc)
            report["rows_rejected"] = len(quarantine)
            self._write_report(report, quarantine, row_log)
            return report

        report["rows_rejected"] = sum(1 for entry in row_log if entry["status"] == "rejected")
        report["rows_ignored"] = sum(
            1 for entry in row_log if entry["status"] == "ignored_exact_duplicate"
        )
        if not candidates:
            report["status"] = "quarantined" if quarantine else "empty"
            self._write_report(report, quarantine, row_log)
            return report

        connection = None
        try:
            table = self._clean_name(table_name)
            self.db_config["database"] = self.database
            connection = pymysql.connect(**self.db_config)
            with connection.cursor() as cursor:
                self._validate_target(cursor, table, columns, keys, numeric)
                insert_columns = ", ".join(self._quote_id(column) for column in columns)
                placeholders = ", ".join(["%s"] * len(columns))
                update_columns = [column for column in columns if column not in keys]
                updates = ", ".join(
                    f"{self._quote_id(column)}=VALUES({self._quote_id(column)})"
                    for column in update_columns
                )
                if not updates:
                    first_key = self._quote_id(keys[0])
                    updates = f"{first_key}=VALUES({first_key})"
                statement = (
                    f"INSERT INTO {self._quote_id(self.database)}.{self._quote_id(table)} "
                    f"({insert_columns}) VALUES ({placeholders}) "
                    f"ON DUPLICATE KEY UPDATE {updates}"
                )

                connection.begin()
                try:
                    for row_number, row, row_hash in candidates:
                        cursor.execute(statement, tuple(row.get(column) for column in columns))
                        if cursor.rowcount == 1:
                            report["rows_inserted"] += 1
                            status = "inserted"
                        elif cursor.rowcount == 2:
                            report["rows_updated"] += 1
                            status = "updated"
                        elif cursor.rowcount == 0:
                            report["rows_ignored"] += 1
                            status = "ignored_unchanged"
                        else:
                            raise ImportDatabaseError("Réponse inattendue du serveur pendant l'upsert.")
                        for entry in row_log:
                            if entry["row_number"] == row_number and entry["status"] == "pending_upsert":
                                entry["status"] = status
                                break
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        except ImportValidationError as exc:
            quarantine.extend(
                {"row_number": row_number, "row": row, "errors": [str(exc)]}
                for row_number, row, _ in candidates
            )
            for entry in row_log:
                if entry["status"] == "pending_upsert":
                    entry["status"] = "quarantined_target_validation"
            report["status"] = "quarantined"
            report["validation_error"] = str(exc)
            self._write_report(report, quarantine, row_log)
            return report
        except Exception as exc:
            if connection is not None:
                connection.rollback()
            quarantine.extend(
                {
                    "row_number": row_number,
                    "row": row,
                    "errors": ["Base de données indisponible; lignes non importées."],
                }
                for row_number, row, _ in candidates
            )
            for entry in row_log:
                if entry["status"] in {"pending_upsert", "inserted", "updated", "ignored_unchanged"}:
                    entry["status"] = "quarantined_database_failure"
            report["rows_inserted"] = 0
            report["rows_updated"] = 0
            report["status"] = "failed"
            report["database_error_type"] = type(exc).__name__
            self._write_report(report, quarantine, row_log)
            raise ImportDatabaseError(
                f"Import non validé, transaction annulée; batch={batch_id}, "
                f"erreur={type(exc).__name__}."
            ) from exc
        finally:
            if connection is not None:
                connection.close()

        report["status"] = "committed"
        self._write_report(report, quarantine, row_log)
        return report
