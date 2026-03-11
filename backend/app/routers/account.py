from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import AuthenticatedUser, create_session_token
from app.dependencies import get_current_user, get_settings, get_usage_store
from app.schemas import AccountSuccessResponse, LoginRequest, LoginResponseData, LoginSuccessResponse
from app.services.usage_store import UsageStore
from app.settings import Settings

router = APIRouter(prefix="/api", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginSuccessResponse,
    responses={
        401: {"description": "Invalid credentials"},
    },
)
async def login(
    payload: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    usage_store: Annotated[UsageStore, Depends(get_usage_store)],
) -> LoginSuccessResponse:
    authenticated_user = usage_store.authenticate_user(payload.username, payload.password)
    account = usage_store.get_account_summary(authenticated_user)
    token = create_session_token(authenticated_user, settings.auth_secret)

    return LoginSuccessResponse(data=LoginResponseData(token=token, account=account))


@router.get(
    "/account",
    response_model=AccountSuccessResponse,
    responses={
        401: {"description": "Authentication required"},
    },
)
async def get_account(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    usage_store: Annotated[UsageStore, Depends(get_usage_store)],
) -> AccountSuccessResponse:
    return AccountSuccessResponse(data=usage_store.get_account_summary(current_user))
