"""Charge le CSV des cultures dans MySQL (à relancer après chaque modification du CSV).

    python bd/connection.py
Identifiants : variables MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bd.config import DB_CONFIG, DB_NAME, TABLE_CULTURE
from bd.mysql_ingestor import MySQLIngestor

CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cultures_completes_8_especes_v6.csv")

if __name__ == "__main__":
    ingestor = MySQLIngestor(db_config=DB_CONFIG, database=DB_NAME)
    nb = ingestor.ingest(CSV, table_name=TABLE_CULTURE, truncate=True)
    print(f"{nb} lignes insérées dans {DB_NAME}.{TABLE_CULTURE}.")
