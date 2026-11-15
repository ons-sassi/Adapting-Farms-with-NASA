from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import PROJECT_ROOT, Settings
from app.services import indicateur_service


def test_gee_settings_load_from_dotenv_template(monkeypatch):
    for key in ("GEE_PROJECT", "GEE_SERVICE_ACCOUNT", "GEE_KEY_FILE"):
        monkeypatch.delenv(key, raising=False)

    configured = Settings(_env_file=PROJECT_ROOT / ".env.example")

    assert configured.gee_project == "your-google-cloud-project-id"
    assert configured.gee_service_account == "gee-service-account@your-project.iam.gserviceaccount.com"
    assert configured.gee_key_file == "path/to/protected/service-account-key.json"


def test_indicator_service_passes_settings_to_existing_gee_initializer(monkeypatch):
    from common import connectors

    settings = SimpleNamespace(
        gee_project="test-project",
        gee_service_account="service@test-project.iam.gserviceaccount.com",
        gee_key_file="protected/test-key.json",
    )
    calls = []
    monkeypatch.setattr(indicateur_service, "settings", settings)
    monkeypatch.setattr(connectors, "init_gee", lambda **kwargs: calls.append(kwargs))

    indicateur_service._engine()

    assert calls == [{
        "project": "test-project",
        "service_account": "service@test-project.iam.gserviceaccount.com",
        "key_file": "protected/test-key.json",
    }]


def test_indicator_service_requires_service_account_pair(monkeypatch):
    from common import connectors

    monkeypatch.setattr(
        indicateur_service, "settings",
        SimpleNamespace(gee_project="test-project", gee_service_account="account", gee_key_file=""),
    )
    monkeypatch.setattr(connectors, "init_gee", lambda **kwargs: pytest.fail("must not initialize GEE"))

    with pytest.raises(HTTPException, match="GEE_SERVICE_ACCOUNT et GEE_KEY_FILE"):
        indicateur_service._engine()
