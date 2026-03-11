from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_provider_adapter
from app.factory import create_app
from app.settings import Settings
from tests.helpers import StubAdapter


@pytest.fixture
def settings() -> Settings:
    return Settings(
        proxy_api_key="test-key",
        proxy_url="https://example.com/v1/chat/completions",
        model_name="nano-banana-2",
        cors_origins=["http://localhost:3100"],
        request_timeout_seconds=60,
    )


@pytest.fixture
def client(settings: Settings) -> Generator[TestClient, None, None]:
    app = create_app(settings)
    app.dependency_overrides[get_provider_adapter] = lambda: StubAdapter()

    with TestClient(app) as test_client:
        yield test_client
