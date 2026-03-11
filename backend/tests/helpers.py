from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from app.auth import AuthenticatedUser
from app.errors import AuthenticationError, UsageLimitError
from app.schemas import AccountSummary


class StubAdapter:
    def __init__(self, result: str = "https://example.com/result.png", exc: Exception | None = None) -> None:
        self._result = result
        self._exc = exc

    async def process_image(self, image_bytes: bytes, image_mime: str, prompt: str) -> str:
        if self._exc is not None:
            raise self._exc
        return self._result


def create_session_token(
    username: str,
    role: str,
    secret: str,
    expires_at: int | None = None,
) -> str:
    resolved_expires_at = expires_at or int(time.time()) + 3600
    payload = json.dumps({"u": username, "r": role, "exp": resolved_expires_at}, separators=(",", ":"))
    payload_segment = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    signature_segment = base64.urlsafe_b64encode(
        hmac.new(secret.encode("utf-8"), payload_segment.encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    return f"{payload_segment}.{signature_segment}"


class StubUsageStore:
    def __init__(
        self,
        admin_username: str = "admin",
        admin_password: str = "admin123",
        guest_username: str = "guest",
        guest_password: str = "guest123",
        guest_usage_limit: int = 100,
    ) -> None:
        self._users = {
            admin_username: {
                "password": admin_password,
                "role": "admin",
                "usage_count": 0,
                "usage_limit": None,
                "reserved_generations": 0,
            },
            guest_username: {
                "password": guest_password,
                "role": "guest",
                "usage_count": 0,
                "usage_limit": guest_usage_limit,
                "reserved_generations": 0,
            },
        }

    def authenticate_user(self, username: str, password: str) -> AuthenticatedUser:
        user = self._users.get(username)
        if user is None or user["password"] != password:
            raise AuthenticationError("帳號或密碼不正確。", code="INVALID_CREDENTIALS")

        return AuthenticatedUser(username=username, role=user["role"])

    def get_account_summary(self, user: AuthenticatedUser) -> AccountSummary:
        record = self._get_user_record(user)
        usage_limit = record["usage_limit"]
        usage_count = record["usage_count"]
        remaining_generations = None if usage_limit is None else max(0, usage_limit - usage_count)
        return AccountSummary(
            username=user.username,
            role=user.role,
            usage_count=usage_count,
            usage_limit=usage_limit,
            remaining_generations=remaining_generations,
            is_limited=usage_limit is not None and usage_count >= usage_limit,
        )

    def reserve_generation_slot(self, user: AuthenticatedUser) -> None:
        record = self._get_user_record(user)
        usage_limit = record["usage_limit"]

        if usage_limit is None:
            return

        if record["usage_count"] + record["reserved_generations"] >= usage_limit:
            raise UsageLimitError()

        record["reserved_generations"] += 1

    def complete_generation(self, user: AuthenticatedUser) -> AccountSummary:
        record = self._get_user_record(user)
        if record["usage_limit"] is not None:
            record["reserved_generations"] = max(0, record["reserved_generations"] - 1)
            record["usage_count"] += 1
        return self.get_account_summary(user)

    def release_reserved_generation(self, user: AuthenticatedUser) -> None:
        record = self._get_user_record(user)
        if record["usage_limit"] is not None:
            record["reserved_generations"] = max(0, record["reserved_generations"] - 1)

    def record_successful_generation(self, user: AuthenticatedUser) -> AccountSummary:
        record = self._get_user_record(user)
        if record["usage_limit"] is not None and record["usage_count"] >= record["usage_limit"]:
            raise UsageLimitError()
        record["usage_count"] += 1
        return self.get_account_summary(user)

    def _get_user_record(self, user: AuthenticatedUser) -> dict[str, int | str | None]:
        record = self._users.get(user.username)
        if record is None or record["role"] != user.role:
            raise AuthenticationError("登入資訊無效，請重新登入。", code="INVALID_SESSION")
        return record
