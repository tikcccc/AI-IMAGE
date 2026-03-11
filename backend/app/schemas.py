from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, HttpUrl


class ProcessImageResponseData(BaseModel):
    result_image: str | HttpUrl


class ProcessImageSuccessResponse(BaseModel):
    status: Literal["success"] = "success"
    data: ProcessImageResponseData


class ErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    message: str
    code: str

