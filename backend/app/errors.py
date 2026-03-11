from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas import ErrorResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, message: str, code: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class InvalidInputError(AppError):
    def __init__(self, message: str, code: str = "INVALID_INPUT") -> None:
        super().__init__(message=message, code=code, status_code=status.HTTP_400_BAD_REQUEST)


class ProviderTimeoutError(AppError):
    def __init__(self, message: str = "第三方服務逾時，請稍後再試。") -> None:
        super().__init__(
            message=message,
            code="PROVIDER_TIMEOUT",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        )


class ProviderResponseError(AppError):
    def __init__(self, message: str = "圖片處理服務回應異常。") -> None:
        super().__init__(
            message=message,
            code="PROVIDER_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(message=exc.message, code=exc.code).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        message = "請確認圖片與 prompt 欄位都已正確提供。"
        if exc.errors():
            message = exc.errors()[0].get("msg", message)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(message=message, code="INVALID_INPUT").model_dump(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server error", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                message="伺服器發生未預期錯誤，請稍後再試。",
                code="INTERNAL_ERROR",
            ).model_dump(),
        )

