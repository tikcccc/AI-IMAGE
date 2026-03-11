from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser
from app.dependencies import get_provider_adapter
from app.factory import create_app
from app.errors import ProviderResponseError, ProviderTimeoutError
from app.services.provider import VectorEngineAdapter
from app.settings import Settings
from tests.helpers import StubAdapter, StubUsageStore, create_session_token


def test_process_image_returns_success_payload(client, admin_auth_headers) -> None:
    response = client.post(
        "/api/process-image",
        data={"prompt": "make it cinematic"},
        files={"image": ("sample.png", b"fake-image", "image/png")},
        headers=admin_auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "data": {
            "result_image": "https://example.com/result.png",
            "account": {
                "username": "admin",
                "role": "admin",
                "usage_count": 0,
                "usage_limit": None,
                "remaining_generations": None,
                "is_limited": False,
            },
        },
    }


def test_process_image_requires_authentication(client) -> None:
    response = client.post(
        "/api/process-image",
        data={"prompt": "make it cinematic"},
        files={"image": ("sample.png", b"fake-image", "image/png")},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "AUTH_REQUIRED"


def test_process_image_rejects_empty_prompt(client, admin_auth_headers) -> None:
    response = client.post(
        "/api/process-image",
        data={"prompt": "   "},
        files={"image": ("sample.png", b"fake-image", "image/png")},
        headers=admin_auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_PROMPT"


def test_process_image_rejects_unsupported_type(client, admin_auth_headers) -> None:
    response = client.post(
        "/api/process-image",
        data={"prompt": "enhance"},
        files={"image": ("sample.txt", b"not-an-image", "text/plain")},
        headers=admin_auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "UNSUPPORTED_IMAGE_TYPE"


def test_process_image_rejects_file_over_5mb(client, admin_auth_headers) -> None:
    oversized_payload = b"a" * (5 * 1024 * 1024 + 1)
    response = client.post(
        "/api/process-image",
        data={"prompt": "enhance"},
        files={"image": ("large.png", oversized_payload, "image/png")},
        headers=admin_auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "IMAGE_TOO_LARGE"


def test_login_returns_session_token(client) -> None:
    response = client.post(
        "/api/login",
        json={"username": "admin", "password": "admin123"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["account"]["username"] == "admin"
    assert isinstance(payload["data"]["token"], str)
    assert payload["data"]["token"]


def test_login_rejects_invalid_credentials(client) -> None:
    response = client.post(
        "/api/login",
        json={"username": "admin", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_account_returns_guest_usage_summary(client, guest_auth_headers) -> None:
    response = client.get("/api/account", headers=guest_auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "data": {
            "username": "guest",
            "role": "guest",
            "usage_count": 0,
            "usage_limit": 100,
            "remaining_generations": 100,
            "is_limited": False,
        },
    }


def test_process_image_increments_guest_usage(client, guest_auth_headers) -> None:
    response = client.post(
        "/api/process-image",
        data={"prompt": "enhance"},
        files={"image": ("sample.png", b"fake-image", "image/png")},
        headers=guest_auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["account"] == {
        "username": "guest",
        "role": "guest",
        "usage_count": 1,
        "usage_limit": 100,
        "remaining_generations": 99,
        "is_limited": False,
    }


def test_process_image_blocks_guest_after_limit(client, guest_auth_headers) -> None:
    usage_store = client.app.state.usage_store
    guest_user = AuthenticatedUser(username="guest", role="guest")

    for _ in range(100):
        usage_store.record_successful_generation(guest_user)

    response = client.post(
        "/api/process-image",
        data={"prompt": "enhance"},
        files={"image": ("sample.png", b"fake-image", "image/png")},
        headers=guest_auth_headers,
    )

    assert response.status_code == 429
    assert response.json()["code"] == "GUEST_USAGE_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_adapter_returns_first_image_url(settings: Settings) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": "https://cdn.example.com/output.png"},
                                }
                            ]
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        adapter = VectorEngineAdapter(settings=settings, client=http_client)
        result = await adapter.process_image(b"demo", "image/png", "enhance")

    assert result == "https://cdn.example.com/output.png"


@pytest.mark.asyncio
async def test_adapter_parses_markdown_image_url(settings: Settings) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "結果如下：![generated](https://cdn.example.com/generated.webp)"
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        adapter = VectorEngineAdapter(settings=settings, client=http_client)
        result = await adapter.process_image(b"demo", "image/png", "enhance")

    assert result == "https://cdn.example.com/generated.webp"


@pytest.mark.asyncio
async def test_adapter_maps_timeout_error(settings: Settings) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timeout")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        adapter = VectorEngineAdapter(settings=settings, client=http_client)
        with pytest.raises(ProviderTimeoutError):
            await adapter.process_image(b"demo", "image/png", "enhance")


@pytest.mark.asyncio
async def test_adapter_maps_unexpected_response(settings: Settings) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": "no image returned"}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        adapter = VectorEngineAdapter(settings=settings, client=http_client)
        with pytest.raises(ProviderResponseError):
            await adapter.process_image(b"demo", "image/png", "enhance")


def test_process_image_maps_provider_timeout(settings: Settings) -> None:
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
    app.dependency_overrides[get_provider_adapter] = lambda: StubAdapter(exc=ProviderTimeoutError())

    with TestClient(app) as client:
        response = client.post(
            "/api/process-image",
            data={"prompt": "enhance"},
            files={"image": ("sample.png", b"fake-image", "image/png")},
            headers={"Authorization": f"Bearer {create_session_token('admin', 'admin', settings.auth_secret)}"},
        )

    assert response.status_code == 504
    assert response.json()["code"] == "PROVIDER_TIMEOUT"


def test_process_image_maps_provider_error(settings: Settings) -> None:
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
    app.dependency_overrides[get_provider_adapter] = lambda: StubAdapter(exc=ProviderResponseError())

    with TestClient(app) as client:
        response = client.post(
            "/api/process-image",
            data={"prompt": "enhance"},
            files={"image": ("sample.png", b"fake-image", "image/png")},
            headers={"Authorization": f"Bearer {create_session_token('admin', 'admin', settings.auth_secret)}"},
        )

    assert response.status_code == 502
    assert response.json()["code"] == "PROVIDER_ERROR"
