"""Importe une seule fois les anciens datasets JSON locaux vers MySQL."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.integrations.agri_external_data_collector.collector import sync_legacy_files_to_database

if __name__ == "__main__":
    print(json.dumps(sync_legacy_files_to_database(), ensure_ascii=False, indent=2))
