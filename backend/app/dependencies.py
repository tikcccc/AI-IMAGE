from __future__ import annotations

from fastapi import Depends, Request

from app.services.provider import VectorEngineAdapter
from app.settings import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_provider_adapter(settings: Settings = Depends(get_settings)) -> VectorEngineAdapter:
    return VectorEngineAdapter(settings=settings)

