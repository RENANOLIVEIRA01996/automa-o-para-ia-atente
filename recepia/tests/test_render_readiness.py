"""Checks for Render liveness and private Evolution configuration."""
from pydantic import ValidationError
import pytest

from config import Settings
from database import get_db_dependency
from main import app


def test_health_does_not_depend_on_database(client):
    def failing_db():
        raise AssertionError("/health must not open a database session")
        yield

    app.dependency_overrides[get_db_dependency] = failing_db
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_database_failure(client):
    class FailingSession:
        def execute(self, _):
            raise RuntimeError("database unavailable")

    def failing_db():
        yield FailingSession()

    app.dependency_overrides[get_db_dependency] = failing_db
    response = client.get("/ready")
    assert response.status_code == 503


def test_render_private_hostport_overrides_local_evolution_url():
    settings = Settings(
        JWT_SECRET="x" * 40,
        ADMIN_API_KEY="safe-admin-key",
        EVOLUTION_WEBHOOK_SECRET="safe-webhook-key",
        EVOLUTION_API_URL="http://evolution:8080",
        EVOLUTION_API_HOSTPORT="evolution-abc:8080",
    )
    assert settings.evolution_base_url == "http://evolution-abc:8080"


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError):
        Settings(
            JWT_SECRET="x" * 40,
            ADMIN_API_KEY="safe-admin-key",
            EVOLUTION_WEBHOOK_SECRET="safe-webhook-key",
            DEBUG=False,
            ALLOWED_ORIGINS="https://example.com, *",
        )
