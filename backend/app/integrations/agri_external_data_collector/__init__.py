"""Collecte de données agricoles externes (hors saisie fermier et satellites)."""
from .sources import SOURCES
from .collector import collect_source
__all__ = ["SOURCES", "collect_source"]
