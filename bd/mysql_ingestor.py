import json
import os
import re
import unicodedata
from datetime import datetime, timezone
import pandas as pd
import pymysql


class MySQLIngestor:
    TYPE_MAP = {
        "Int64": "BIGINT",
        "int64": "BIGINT",
        "Float64": "DOUBLE",
        "float64": "DOUBLE",
        "boolean": "TINYINT(1)",
        "bool": "TINYINT(1)",
        "datetime64[ns]": "DATETIME(6)",
        "string": "LONGTEXT",
        "object": "LONGTEXT",
    }

    def __init__(self, db_config: dict, database: str):
        """
        db_config : dict contenant host, user, password, port (ex: {"host": "localhost", "user": "root", "password": "123"})
        database  : nom de la base de données MySQL cible
        """
        self.db_config = {**db_config, "charset": "utf8mb4"}
        self.database = self._clean_name(database)

    @staticmethod
    def _clean_name(name: str) -> str:
        name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", name.lower()).strip("_")
        # MySQL limite les identifiants à 64 caractères
        cleaned = cleaned[:64]
        return f"col_{cleaned}" if cleaned and cleaned[0].isdigit() else (cleaned or "col_unnamed")

    @staticmethod
    def _quote_id(identifier: str) -> str:
        return f"`{identifier.replace('`', '``')}`"

    def _read_file(self, filepath: str) -> tuple[pd.DataFrame, set[str]]:
        ext = os.path.splitext(filepath)[1].lower()
        json_cols = set()

        if ext == ".csv":
            df = pd.read_csv(filepath, sep=None, engine="python")
        elif ext in {".json", ".jsonl"}:
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    f.seek(0)
                    data = [json.loads(line) for line in f if line.strip()]
            df = pd.json_normalize(data, sep="_")
        else:
            raise ValueError(f"Format non supporté : {ext}")

        # Normalisation des noms de colonnes
        df.columns = [self._clean_name(c) for c in df.columns]

        # Sérialisation des listes/objets imbriqués restants pour le type JSON natif de MySQL
        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, (list, dict))).any():
                json_cols.add(col)
                df[col] = df[col].apply(
                    lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else x
                )

        df = df.convert_dtypes()

        # Colonnes de traçabilité
        df["_source_file"] = os.path.basename(filepath)
        df["_ingested_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        return df, json_cols

    def _infer_mysql_type(self, col: str, dtype, json_cols: set[str]) -> str:
        if col in json_cols:
            return "JSON"
        return self.TYPE_MAP.get(str(dtype), "LONGTEXT")

    def _sync_table_schema(self, cur, table: str, df: pd.DataFrame, json_cols: set[str]):
        db_quoted = self._quote_id(self.database)
        tbl_quoted = self._quote_id(table)

        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS {db_quoted} "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        )
        cur.execute(f"USE {db_quoted};")

        # Vérifier les colonnes existantes
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s;
            """,
            (self.database, table),
        )
        existing_cols = {row[0].lower() for row in cur.fetchall()}

        if not existing_cols:
            # Cas 1 : La table n'existe pas -> Création
            cols_def = [
                f"  {self._quote_id(col)} {self._infer_mysql_type(col, df[col].dtype, json_cols)}"
                for col in df.columns
            ]
            create_stmt = (
                f"CREATE TABLE {db_quoted}.{tbl_quoted} (\n"
                + ",\n".join(cols_def)
                + "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
            )
            cur.execute(create_stmt)
        else:
            # Cas 2 : La table existe -> Ajout des nouvelles colonnes uniquement
            for col in df.columns:
                if col.lower() not in existing_cols:
                    mysql_type = self._infer_mysql_type(col, df[col].dtype, json_cols)
                    alter_stmt = (
                        f"ALTER TABLE {db_quoted}.{tbl_quoted} "
                        f"ADD COLUMN {self._quote_id(col)} {mysql_type};"
                    )
                    cur.execute(alter_stmt)

    def ingest(self, filepath: str, table_name: str, batch_size: int = 5000, truncate: bool = False) -> int:
        """Lit un CSV/JSON, crée ou met à jour la table MySQL, et ajoute les lignes par lots.
        truncate=True vide la table avant l'insertion (évite les doublons en cas de ré-exécution)."""
        table = self._clean_name(table_name)
        df, json_cols = self._read_file(filepath)

        if df.empty:
            return 0

        # Conversion stricte des NA/NaN pandas en None Python pour pymysql
        df_clean = df.astype(object).where(pd.notnull(df), None)
        rows = list(df_clean.itertuples(index=False, name=None))

        cols_quoted = ", ".join(self._quote_id(c) for c in df.columns)
        placeholders = ", ".join(["%s"] * len(df.columns))
        insert_stmt = (
            f"INSERT INTO {self._quote_id(self.database)}.{self._quote_id(table)} "
            f"({cols_quoted}) VALUES ({placeholders})"
        )

        conn = pymysql.connect(**self.db_config)
        try:
            with conn.cursor() as cur:
                self._sync_table_schema(cur, table, df, json_cols)
                if truncate:
                    cur.execute(f"TRUNCATE TABLE {self._quote_id(self.database)}.{self._quote_id(table)}")

                for i in range(0, len(rows), batch_size):
                    cur.executemany(insert_stmt, rows[i : i + batch_size])

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

        return len(rows)