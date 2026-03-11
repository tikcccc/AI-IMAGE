from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.errors import register_exception_handlers
from app.routers.account import router as account_router
from app.routers.process_image import router as process_image_router
from app.services.usage_store import UsageStore
from app.settings import Settings


def create_app(settings: Settings | None = None, usage_store: UsageStore | None = None) -> FastAPI:
    resolved_settings = settings or Settings()

    app = FastAPI(
        title="AI Image Processing Demo API",
        version="0.1.0",
    )
    app.state.settings = resolved_settings
    resolved_usage_store = usage_store or UsageStore(resolved_settings)
    if usage_store is None:
        resolved_usage_store.initialize()
    app.state.usage_store = resolved_usage_store

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(account_router)
    app.include_router(process_image_router)

    return app
