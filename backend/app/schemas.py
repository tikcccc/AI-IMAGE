from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, HttpUrl


class AccountSummary(BaseModel):
    username: str
    role: Literal["admin", "guest"]
    usage_count: int
    usage_limit: int | None = None
    remaining_generations: int | None = None
    is_limited: bool


class ProcessImageResponseData(BaseModel):
    account: AccountSummary
    result_image: str | HttpUrl


class ProcessImageSuccessResponse(BaseModel):
    status: Literal["success"] = "success"
    data: ProcessImageResponseData


class AccountSuccessResponse(BaseModel):
    status: Literal["success"] = "success"
    data: AccountSummary


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponseData(BaseModel):
    token: str
    account: AccountSummary


class LoginSuccessResponse(BaseModel):
    status: Literal["success"] = "success"
    data: LoginResponseData


class ErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    message: str
    code: str
