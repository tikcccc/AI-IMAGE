from __future__ import annotations

import base64
import re
from collections.abc import Mapping
from typing import Any

import httpx

from app.errors import ProviderResponseError, ProviderTimeoutError
from app.settings import Settings

MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*]\((https?://[^)\s]+)\)")
HTTP_URL_PATTERN = re.compile(r"https?://[^\s)>\"]+")
DATA_URL_PATTERN = re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]+")


class VectorEngineAdapter:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client

    async def process_image(self, image_bytes: bytes, image_mime: str, prompt: str) -> str:
        payload = self._build_payload(image_bytes=image_bytes, image_mime=image_mime, prompt=prompt)

        try:
            response = await self._post(payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError() from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderResponseError(
                f"中轉站處理失敗：{self._extract_provider_error(exc.response)}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderResponseError("無法連線到圖片處理服務。") from exc

        try:
            response_data = response.json()
        except ValueError as exc:
            raise ProviderResponseError("中轉站回傳了無法解析的 JSON。") from exc

        result_image = self.extract_result_image(response_data)
        if not result_image:
            raise ProviderResponseError("中轉站回應中找不到可用的圖片結果。")
        return result_image

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        if self._client is not None:
            return await self._client.post(
                self._settings.proxy_url,
                headers=self._build_headers(),
                json=payload,
            )

        async with httpx.AsyncClient(timeout=self._settings.request_timeout_seconds) as client:
            return await client.post(
                self._settings.proxy_url,
                headers=self._build_headers(),
                json=payload,
            )

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.proxy_api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, image_bytes: bytes, image_mime: str, prompt: str) -> dict[str, Any]:
        encoded_image = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:{image_mime};base64,{encoded_image}"

        return {
            "model": self._settings.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            "stream": False,
        }

    @classmethod
    def extract_result_image(cls, payload: Any) -> str | None:
        for candidate in cls._iter_candidate_urls(payload):
            if candidate:
                return candidate
        return None

    @classmethod
    def _iter_candidate_urls(cls, payload: Any) -> list[str]:
        urls: list[str] = []

        if isinstance(payload, Mapping):
            for path in ("output", "data", "images"):
                value = payload.get(path)
                urls.extend(cls._extract_from_value(value))

            choices = payload.get("choices")
            if isinstance(choices, list):
                for choice in choices:
                    if not isinstance(choice, Mapping):
                        continue
                    urls.extend(cls._extract_from_value(choice.get("message")))
                    urls.extend(cls._extract_from_value(choice.get("delta")))
                    urls.extend(cls._extract_from_value(choice.get("content")))

            urls.extend(cls._extract_from_value(payload.get("message")))
            urls.extend(cls._extract_from_value(payload.get("content")))

        return [item for item in urls if item]

    @classmethod
    def _extract_from_value(cls, value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            return cls._extract_from_text(value)

        if isinstance(value, Mapping):
            urls: list[str] = []
            direct = cls._extract_direct_url(value)
            if direct:
                urls.append(direct)

            for key in ("image_url", "url", "image", "result_image", "content", "images", "data"):
                if key in value:
                    urls.extend(cls._extract_from_value(value[key]))
            return urls

        if isinstance(value, list):
            urls: list[str] = []
            for item in value:
                urls.extend(cls._extract_from_value(item))
            return urls

        return []

    @classmethod
    def _extract_direct_url(cls, value: Mapping[str, Any]) -> str | None:
        for key in ("url", "image", "result_image"):
            url = value.get(key)
            if isinstance(url, str) and cls._is_supported_result(url):
                return url

        image_url = value.get("image_url")
        if isinstance(image_url, str) and cls._is_supported_result(image_url):
            return image_url
        if isinstance(image_url, Mapping):
            nested_url = image_url.get("url")
            if isinstance(nested_url, str) and cls._is_supported_result(nested_url):
                return nested_url
        return None

    @classmethod
    def _extract_from_text(cls, content: str) -> list[str]:
        candidates: list[str] = []
        candidates.extend(MARKDOWN_IMAGE_PATTERN.findall(content))
        candidates.extend(DATA_URL_PATTERN.findall(content))

        for match in HTTP_URL_PATTERN.findall(content):
            if cls._is_supported_result(match):
                candidates.append(match)

        return candidates

    @staticmethod
    def _is_supported_result(value: str) -> bool:
        return value.startswith("http://") or value.startswith("https://") or value.startswith("data:image/")

    @staticmethod
    def _extract_provider_error(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text or f"HTTP {response.status_code}"

        if isinstance(payload, Mapping):
            error = payload.get("error")
            if isinstance(error, Mapping):
                return str(error.get("message") or error.get("code") or response.status_code)
            return str(payload.get("message") or payload.get("detail") or response.status_code)

        return str(payload)

