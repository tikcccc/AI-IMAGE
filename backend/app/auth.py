from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Literal

from app.errors import AuthenticationError

UserRole = Literal["admin", "guest"]
SESSION_TTL_SECONDS = 60 * 60 * 24 * 7


@dataclass(frozen=True)
class AuthenticatedUser:
    username: str
    role: UserRole


def _decode_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _encode_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def create_session_token(
    user: AuthenticatedUser,
    secret: str,
    expires_at: int | None = None,
) -> str:
    payload = json.dumps(
        {
            "u": user.username,
            "r": user.role,
            "exp": expires_at or int(time.time()) + SESSION_TTL_SECONDS,
        },
        separators=(",", ":"),
    )
    payload_segment = _encode_base64url(payload.encode("utf-8"))
    signature_segment = _encode_base64url(
        hmac.new(
            secret.encode("utf-8"),
            payload_segment.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )
    return f"{payload_segment}.{signature_segment}"


def verify_session_token(token: str, secret: str) -> AuthenticatedUser:
    payload_segment, separator, signature_segment = token.partition(".")
    if not payload_segment or separator != "." or not signature_segment:
        raise AuthenticationError("The session is invalid. Please sign in again.", code="INVALID_SESSION")

    expected_signature = _encode_base64url(
        hmac.new(
            secret.encode("utf-8"),
            payload_segment.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    )
    if not hmac.compare_digest(expected_signature, signature_segment):
        raise AuthenticationError("The session is invalid. Please sign in again.", code="INVALID_SESSION")

    try:
        payload = json.loads(_decode_base64url(payload_segment).decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise AuthenticationError("The session is invalid. Please sign in again.", code="INVALID_SESSION") from exc

    username = payload.get("u")
    role = payload.get("r")
    expires_at = payload.get("exp")

    if not isinstance(username, str) or not isinstance(role, str) or not isinstance(expires_at, int):
        raise AuthenticationError("The session is invalid. Please sign in again.", code="INVALID_SESSION")

    if not username.strip() or role not in {"admin", "guest"}:
        raise AuthenticationError("The session is invalid. Please sign in again.", code="INVALID_SESSION")

    if expires_at <= int(time.time()):
        raise AuthenticationError("The session has expired. Please sign in again.", code="INVALID_SESSION")

    return AuthenticatedUser(username=username, role=role)
