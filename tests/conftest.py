"""Configuration pytest : chemin du projet, cache isolé, catalogue de cultures (CSV réel)."""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common import connectors as cn  # noqa: E402


@pytest.fixture(autouse=True)
def cache_isole(tmp_path, monkeypatch):
    """Chaque test écrit son cache dans un dossier temporaire (jamais .cache_indicateurs)."""
    monkeypatch.setattr(cn, "CACHE_DIR", tmp_path / "cache")


@pytest.fixture
def catalogue_csv(monkeypatch):
    """Catalogue de cultures réel lu dans le CSV chargé en base (pas besoin de MySQL)."""
    from bd import cultures
    csv = ROOT / "bd" / "data" / "cultures_completes_8_especes_v6.csv"
    monkeypatch.setattr(cultures, "_lire_table", lambda: cultures.lire_csv(str(csv)))
    cultures.recharger()
    yield cultures
    cultures.recharger()
