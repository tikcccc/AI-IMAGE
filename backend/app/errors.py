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


class AuthenticationError(AppError):
    def __init__(
        self,
        message: str = "Sign in first.",
        code: str = "AUTH_REQUIRED",
        status_code: int = status.HTTP_401_UNAUTHORIZED,
    ) -> None:
        super().__init__(message=message, code=code, status_code=status_code)


class UsageLimitError(AppError):
    def __init__(self, message: str = "The guest account has reached the 100-image generation limit.") -> None:
        super().__init__(
            message=message,
            code="GUEST_USAGE_LIMIT_REACHED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class ProviderTimeoutError(AppError):
    def __init__(self, message: str = "The upstream service timed out. Please try again later.") -> None:
        super().__init__(
            message=message,
            code="PROVIDER_TIMEOUT",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        )


class ProviderResponseError(AppError):
    def __init__(self, message: str = "The image processing service returned an unexpected response.") -> None:
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
        message = "Make sure both the image and prompt fields are provided correctly."
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
                message="The server encountered an unexpected error. Please try again later.",
                code="INTERNAL_ERROR",
            ).model_dump(),
        )
