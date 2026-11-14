"""Paramètres de connexion MySQL (variables d'environnement, avec valeurs locales par défaut)."""
import os

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
}
DB_NAME = os.getenv("MYSQL_DATABASE", "nasa_challenge")
TABLE_CULTURE = os.getenv("MYSQL_TABLE_CULTURE", "culture")
