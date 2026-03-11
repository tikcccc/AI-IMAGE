from __future__ import annotations

from fastapi import Depends, Header, Request

from app.auth import AuthenticatedUser, verify_session_token
from app.errors import AuthenticationError
from app.services.provider import VectorEngineAdapter
from app.services.usage_store import UsageStore
from app.settings import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_provider_adapter(settings: Settings = Depends(get_settings)) -> VectorEngineAdapter:
    return VectorEngineAdapter(settings=settings)


def get_usage_store(request: Request) -> UsageStore:
    return request.app.state.usage_store


def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    if not authorization:
        raise AuthenticationError()

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationError()

    return verify_session_token(token.strip(), settings.auth_secret)
