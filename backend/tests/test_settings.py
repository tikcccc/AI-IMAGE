from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.factory import create_app
from app.settings import Settings


def test_create_app_without_required_env_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PROXY_API_KEY", raising=False)
    monkeypatch.delenv("PROXY_URL", raising=False)
    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    with pytest.raises(ValidationError):
        create_app()


def test_settings_accept_plain_string_or_csv_cors_origins(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "PROXY_API_KEY=test-key",
                "PROXY_URL=https://example.com/v1/chat/completions",
                "MODEL_NAME=nano-banana-2",
                "CORS_ORIGINS=http://localhost:3100, http://127.0.0.1:3100",
                "REQUEST_TIMEOUT_SECONDS=60",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.cors_origins == [
        "http://localhost:3100",
        "http://127.0.0.1:3100",
    ]


def test_settings_reject_proxy_url_without_endpoint_path(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "PROXY_API_KEY=test-key",
                "PROXY_URL=https://api.vectorengine.ai",
                "MODEL_NAME=nano-banana-2",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="PROXY_URL must include a concrete endpoint path"):
        Settings(_env_file=env_file)
