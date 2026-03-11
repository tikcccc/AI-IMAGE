from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.auth import AuthenticatedUser
from app.dependencies import get_current_user, get_provider_adapter, get_usage_store
from app.errors import InvalidInputError
from app.schemas import ProcessImageResponseData, ProcessImageSuccessResponse
from app.services.provider import VectorEngineAdapter
from app.services.usage_store import UsageStore

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
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    adapter: Annotated[VectorEngineAdapter, Depends(get_provider_adapter)],
    usage_store: Annotated[UsageStore, Depends(get_usage_store)],
) -> ProcessImageSuccessResponse:
    reserved_generation = False
    try:
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise InvalidInputError("Prompt cannot be empty.", code="INVALID_PROMPT")

        content_type = (image.content_type or "").lower()
        if content_type not in ALLOWED_MIME_TYPES:
            raise InvalidInputError(
                "Only JPG, JPEG, PNG, and WEBP images are supported.",
                code="UNSUPPORTED_IMAGE_TYPE",
            )

        image_bytes = await image.read()
        if not image_bytes:
            raise InvalidInputError("Upload a valid image file.", code="EMPTY_IMAGE")
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise InvalidInputError("The uploaded image must be smaller than 5 MB.", code="IMAGE_TOO_LARGE")

        usage_store.reserve_generation_slot(current_user)
        reserved_generation = current_user.role == "guest"
        try:
            result_image = await adapter.process_image(
                image_bytes=image_bytes,
                image_mime=content_type,
                prompt=normalized_prompt,
            )
        except Exception:
            if reserved_generation:
                usage_store.release_reserved_generation(current_user)
            raise
        try:
            account = usage_store.complete_generation(current_user)
        except Exception:
            if reserved_generation:
                usage_store.release_reserved_generation(current_user)
            raise

        return ProcessImageSuccessResponse(
            data=ProcessImageResponseData(result_image=result_image, account=account),
        )
    finally:
        await image.close()
