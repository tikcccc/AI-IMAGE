from __future__ import annotations

import json
from urllib.parse import urlparse
from typing import Annotated

from pydantic import Field, PositiveInt, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )

    proxy_api_key: str = Field(..., alias="PROXY_API_KEY", min_length=1)
    proxy_url: str = Field(..., alias="PROXY_URL", min_length=1)
    model_name: str = Field(..., alias="MODEL_NAME", min_length=1)
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3100"],
        alias="CORS_ORIGINS",
    )
    request_timeout_seconds: PositiveInt = Field(
        default=60,
        alias="REQUEST_TIMEOUT_SECONDS",
    )

    @field_validator("proxy_api_key", "proxy_url", "model_name", mode="before")
    @classmethod
    def strip_required_strings(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
        return value

    @field_validator("proxy_url")
    @classmethod
    def validate_proxy_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("PROXY_URL must start with http:// or https://")
        parsed = urlparse(value)
        if parsed.path in ("", "/"):
            raise ValueError(
                "PROXY_URL must include a concrete endpoint path, for example "
                "https://api.vectorengine.ai/v1/chat/completions"
            )
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if value is None or value == "":
            return ["http://localhost:3100"]
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                return json.loads(raw)
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("CORS_ORIGINS must contain at least one origin")
        for item in value:
            if not item.startswith(("http://", "https://")):
                raise ValueError("Each CORS origin must start with http:// or https://")
        return value
