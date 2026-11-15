"""Connexion indépendante au catalogue cultures (base nasa_challenge par défaut)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

DB_CONFIG = {
 "host": os.getenv("CULTURE_MYSQL_HOST", os.getenv("MYSQL_HOST", "localhost")),
 "port": int(os.getenv("CULTURE_MYSQL_PORT", os.getenv("MYSQL_PORT", "3306"))),
 "user": os.getenv("CULTURE_MYSQL_USER", os.getenv("MYSQL_USER", "root")),
 "password": os.getenv("CULTURE_MYSQL_PASSWORD", os.getenv("MYSQL_PASSWORD", "")),
}
DB_NAME = os.getenv("CULTURE_MYSQL_DATABASE", "nasa_challenge")
TABLE_CULTURE = os.getenv("CULTURE_MYSQL_TABLE", "culture")
