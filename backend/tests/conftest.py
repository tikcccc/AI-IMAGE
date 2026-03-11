from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_provider_adapter
from app.factory import create_app
from app.settings import Settings
from tests.helpers import StubAdapter, StubUsageStore


@pytest.fixture
def settings() -> Settings:
    return Settings(
        proxy_api_key="test-key",
        proxy_url="https://example.com/v1/chat/completions",
        model_name="nano-banana-2",
        database_url="postgresql://user:pass@localhost:5432/demo?sslmode=require",
        auth_secret="test-auth-secret-12345",
        admin_username="admin",
        admin_password="admin123",
        guest_username="guest",
        guest_password="guest123",
        guest_usage_limit=100,
        cors_origins=["http://localhost:3100"],
        request_timeout_seconds=60,
    )


@pytest.fixture
def client(settings: Settings) -> Generator[TestClient, None, None]:
    app = create_app(
        settings,
        usage_store=StubUsageStore(
            admin_username=settings.admin_username,
            admin_password=settings.admin_password,
            guest_username=settings.guest_username,
            guest_password=settings.guest_password,
            guest_usage_limit=settings.guest_usage_limit,
        ),
    )
    app.dependency_overrides[get_provider_adapter] = lambda: StubAdapter()

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_auth_headers(settings: Settings) -> dict[str, str]:
    from tests.helpers import create_session_token

    return {
        "Authorization": f"Bearer {create_session_token('admin', 'admin', settings.auth_secret)}",
    }


@pytest.fixture
def guest_auth_headers(settings: Settings) -> dict[str, str]:
    from tests.helpers import create_session_token

    return {
        "Authorization": f"Bearer {create_session_token('guest', 'guest', settings.auth_secret)}",
    }
