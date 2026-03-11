from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.dependencies import get_provider_adapter
from app.errors import InvalidInputError
from app.schemas import ProcessImageResponseData, ProcessImageSuccessResponse
from app.services.provider import VectorEngineAdapter

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024

router = APIRouter(prefix="/api", tags=["image-processing"])


@router.post(
    "/process-image",
    response_model=ProcessImageSuccessResponse,
    responses={
        400: {"description": "Invalid input"},
        502: {"description": "Provider error"},
        504: {"description": "Provider timeout"},
    },
)
async def process_image(
    image: Annotated[UploadFile, File(...)],
    prompt: Annotated[str, Form(...)],
    adapter: Annotated[VectorEngineAdapter, Depends(get_provider_adapter)],
) -> ProcessImageSuccessResponse:
    try:
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise InvalidInputError("Prompt 不可為空白。", code="INVALID_PROMPT")

        content_type = (image.content_type or "").lower()
        if content_type not in ALLOWED_MIME_TYPES:
            raise InvalidInputError(
                "僅支援 JPG、JPEG、PNG 或 WEBP 圖片。",
                code="UNSUPPORTED_IMAGE_TYPE",
            )

        image_bytes = await image.read()
        if not image_bytes:
            raise InvalidInputError("請上傳一張有效圖片。", code="EMPTY_IMAGE")
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise InvalidInputError("圖片大小不可超過 5MB。", code="IMAGE_TOO_LARGE")

        result_image = await adapter.process_image(
            image_bytes=image_bytes,
            image_mime=content_type,
            prompt=normalized_prompt,
        )

        return ProcessImageSuccessResponse(
            data=ProcessImageResponseData(result_image=result_image),
        )
    finally:
        await image.close()

