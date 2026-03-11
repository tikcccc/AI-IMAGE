from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_provider_adapter
from app.factory import create_app
from app.errors import ProviderResponseError, ProviderTimeoutError
from app.services.provider import VectorEngineAdapter
from app.settings import Settings
from tests.helpers import StubAdapter


def test_process_image_returns_success_payload(client) -> None:
    response = client.post(
        "/api/process-image",
        data={"prompt": "make it cinematic"},
        files={"image": ("sample.png", b"fake-image", "image/png")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "data": {"result_image": "https://example.com/result.png"},
    }


def test_process_image_rejects_empty_prompt(client) -> None:
    response = client.post(
        "/api/process-image",
        data={"prompt": "   "},
        files={"image": ("sample.png", b"fake-image", "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_PROMPT"


def test_process_image_rejects_unsupported_type(client) -> None:
    response = client.post(
        "/api/process-image",
        data={"prompt": "enhance"},
        files={"image": ("sample.txt", b"not-an-image", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "UNSUPPORTED_IMAGE_TYPE"


def test_process_image_rejects_file_over_5mb(client) -> None:
    oversized_payload = b"a" * (5 * 1024 * 1024 + 1)
    response = client.post(
        "/api/process-image",
        data={"prompt": "enhance"},
        files={"image": ("large.png", oversized_payload, "image/png")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "IMAGE_TOO_LARGE"


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
    app = create_app(settings)
    app.dependency_overrides[get_provider_adapter] = lambda: StubAdapter(exc=ProviderTimeoutError())

    with TestClient(app) as client:
        response = client.post(
            "/api/process-image",
            data={"prompt": "enhance"},
            files={"image": ("sample.png", b"fake-image", "image/png")},
        )

    assert response.status_code == 504
    assert response.json()["code"] == "PROVIDER_TIMEOUT"


def test_process_image_maps_provider_error(settings: Settings) -> None:
    app = create_app(settings)
    app.dependency_overrides[get_provider_adapter] = lambda: StubAdapter(exc=ProviderResponseError())

    with TestClient(app) as client:
        response = client.post(
            "/api/process-image",
            data={"prompt": "enhance"},
            files={"image": ("sample.png", b"fake-image", "image/png")},
        )

    assert response.status_code == 502
    assert response.json()["code"] == "PROVIDER_ERROR"
