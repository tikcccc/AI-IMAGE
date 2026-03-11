from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from collections.abc import Mapping
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.auth import AuthenticatedUser
from app.errors import AuthenticationError, UsageLimitError
from app.schemas import AccountSummary
from app.settings import Settings


class UsageStore:
    def __init__(self, settings: Settings) -> None:
        self._database_url = settings.database_url
        self._admin_username = settings.admin_username
        self._admin_password = settings.admin_password
        self._guest_username = settings.guest_username
        self._guest_password = settings.guest_password
        self._guest_usage_limit = settings.guest_usage_limit

    def initialize(self) -> None:
        with self._connect(autocommit=True) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS app_users (
                    username TEXT PRIMARY KEY,
                    password_salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'guest')),
                    usage_count INTEGER NOT NULL DEFAULT 0 CHECK (usage_count >= 0),
                    reserved_generations INTEGER NOT NULL DEFAULT 0 CHECK (reserved_generations >= 0),
                    usage_limit INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            self._upsert_seed_user(
                connection=connection,
                username=self._admin_username,
                password=self._admin_password,
                role="admin",
                usage_limit=None,
            )
            self._upsert_seed_user(
                connection=connection,
                username=self._guest_username,
                password=self._guest_password,
                role="guest",
                usage_limit=self._guest_usage_limit,
            )

    def authenticate_user(self, username: str, password: str) -> AuthenticatedUser:
        normalized_username = username.strip()
        if not normalized_username or not password:
            raise AuthenticationError("The username or password is incorrect.", code="INVALID_CREDENTIALS")

        with self._connect() as connection:
            row = self._fetch_user_row(connection, normalized_username)

        if row is None:
            raise AuthenticationError("The username or password is incorrect.", code="INVALID_CREDENTIALS")

        password_salt = row.get("password_salt")
        password_hash = row.get("password_hash")
        role = row.get("role")

        if (
            not isinstance(password_salt, str)
            or not isinstance(password_hash, str)
            or role not in {"admin", "guest"}
            or not self._verify_password(password, password_salt, password_hash)
        ):
            raise AuthenticationError("The username or password is incorrect.", code="INVALID_CREDENTIALS")

        return AuthenticatedUser(username=normalized_username, role=role)

    def get_account_summary(self, user: AuthenticatedUser) -> AccountSummary:
        with self._connect() as connection:
            row = self._fetch_user_row(connection, user.username)

        return self._build_account_summary(row=row, expected_role=user.role)

    def reserve_generation_slot(self, user: AuthenticatedUser) -> None:
        if user.role != "guest":
            return

        with self._connect() as connection:
            row = connection.execute(
                """
                UPDATE app_users
                SET reserved_generations = reserved_generations + 1,
                    updated_at = NOW()
                WHERE username = %s
                  AND role = %s
                  AND usage_limit IS NOT NULL
                  AND usage_count + reserved_generations < usage_limit
                RETURNING username, role, usage_count, usage_limit
                """,
                (user.username, user.role),
            ).fetchone()

            if row is not None:
                return

            current_row = self._fetch_user_row(connection, user.username)
            self._ensure_user_matches_session(current_row, user.role)

            usage_limit = current_row.get("usage_limit")
            usage_count = current_row.get("usage_count")
            reserved_generations = current_row.get("reserved_generations")
            if (
                isinstance(usage_limit, int)
                and isinstance(usage_count, int)
                and isinstance(reserved_generations, int)
                and usage_count + reserved_generations >= usage_limit
            ):
                raise UsageLimitError()

            raise AuthenticationError("The session is invalid. Please sign in again.", code="INVALID_SESSION")

    def complete_generation(self, user: AuthenticatedUser) -> AccountSummary:
        if user.role != "guest":
            return self.get_account_summary(user)

        with self._connect() as connection:
            row = connection.execute(
                """
                UPDATE app_users
                SET reserved_generations = GREATEST(reserved_generations - 1, 0),
                    usage_count = usage_count + 1,
                    updated_at = NOW()
                WHERE username = %s AND role = %s
                RETURNING username, role, usage_count, usage_limit
                """,
                (user.username, user.role),
            ).fetchone()
            if row is None:
                raise AuthenticationError("The session is invalid. Please sign in again.", code="INVALID_SESSION")

        return self._build_account_summary(row=dict(row), expected_role=user.role)

    def release_reserved_generation(self, user: AuthenticatedUser) -> None:
        if user.role != "guest":
            return

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE app_users
                SET reserved_generations = GREATEST(reserved_generations - 1, 0),
                    updated_at = NOW()
                WHERE username = %s AND role = %s
                """,
                (user.username, user.role),
            )

    def _connect(self, autocommit: bool = False) -> psycopg.Connection[Any]:
        return psycopg.connect(
            self._database_url,
            autocommit=autocommit,
            row_factory=dict_row,
        )

    def _upsert_seed_user(
        self,
        connection: psycopg.Connection[Any],
        username: str,
        password: str,
        role: str,
        usage_limit: int | None,
    ) -> None:
        salt, password_hash = self._hash_password(password)
        connection.execute(
            """
            INSERT INTO app_users (
                username,
                password_salt,
                password_hash,
                role,
                usage_limit
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (username) DO UPDATE
            SET password_salt = EXCLUDED.password_salt,
                password_hash = EXCLUDED.password_hash,
                role = EXCLUDED.role,
                usage_limit = EXCLUDED.usage_limit,
                usage_count = CASE
                    WHEN app_users.role = EXCLUDED.role THEN app_users.usage_count
                    ELSE 0
                END,
                reserved_generations = 0,
                updated_at = NOW()
            """,
            (username, salt, password_hash, role, usage_limit),
        )

    def _fetch_user_row(
        self,
        connection: psycopg.Connection[Any],
        username: str,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            """
            SELECT username, role, password_salt, password_hash, usage_count, reserved_generations, usage_limit
            FROM app_users
            WHERE username = %s
            """,
            (username,),
        ).fetchone()
        return dict(row) if isinstance(row, Mapping) else None

    def _build_account_summary(self, row: dict[str, Any] | None, expected_role: str) -> AccountSummary:
        self._ensure_user_matches_session(row, expected_role)

        usage_count = row.get("usage_count")
        usage_limit = row.get("usage_limit")
        username = row.get("username")
        role = row.get("role")

        if not isinstance(username, str) or role not in {"admin", "guest"} or not isinstance(usage_count, int):
            raise AuthenticationError("The session is invalid. Please sign in again.", code="INVALID_SESSION")

        remaining_generations = (
            max(0, usage_limit - usage_count) if isinstance(usage_limit, int) else None
        )
        return AccountSummary(
            username=username,
            role=role,
            usage_count=usage_count,
            usage_limit=usage_limit if isinstance(usage_limit, int) else None,
            remaining_generations=remaining_generations,
            is_limited=isinstance(usage_limit, int) and usage_count >= usage_limit,
        )

    def _ensure_user_matches_session(self, row: dict[str, Any] | None, expected_role: str) -> None:
        if row is None:
            raise AuthenticationError("The session is invalid. Please sign in again.", code="INVALID_SESSION")

        role = row.get("role")
        if role != expected_role:
            raise AuthenticationError("The session is invalid. Please sign in again.", code="INVALID_SESSION")

    @staticmethod
    def _hash_password(password: str) -> tuple[str, str]:
        salt = secrets.token_bytes(16)
        derived_key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return (
            base64.urlsafe_b64encode(salt).decode("ascii").rstrip("="),
            base64.urlsafe_b64encode(derived_key).decode("ascii").rstrip("="),
        )

    @staticmethod
    def _verify_password(password: str, encoded_salt: str, encoded_hash: str) -> bool:
        padded_salt = encoded_salt + "=" * (-len(encoded_salt) % 4)
        padded_hash = encoded_hash + "=" * (-len(encoded_hash) % 4)
        salt = base64.urlsafe_b64decode(padded_salt)
        expected_hash = base64.urlsafe_b64decode(padded_hash)
        derived_key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(derived_key, expected_hash)
