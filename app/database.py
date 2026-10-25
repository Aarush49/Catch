"""Supabase SDK boundary: HTTPS only, backend credentials, safe public errors."""

import base64
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv
from postgrest.exceptions import APIError
from supabase import create_client
from supabase.client import ClientOptions

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
REQUEST_TIMEOUT_SECONDS = 15


class DatabaseError(RuntimeError):
    """Messages from this boundary are safe for the existing API error handlers."""


class DatabaseConfigurationError(DatabaseError):
    pass


class DatabaseConstraintError(DatabaseError):
    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


def _configuration() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not url or not key:
        raise DatabaseConfigurationError("SUPABASE_URL and SUPABASE_SECRET_KEY are required.")
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https" or not parsed.hostname
            or parsed.username or parsed.password or parsed.path
            or parsed.query or parsed.fragment or parsed.port not in {None, 443}
        ):
            raise ValueError
    except ValueError:
        raise DatabaseConfigurationError("SUPABASE_URL must be the project's HTTPS base URL.") from None
    # Accept the current secret key or a legacy service_role JWT. Decoding a
    # legacy role here only detects a mistaken anon key; Supabase verifies it.
    backend_key = key.startswith("sb_secret_") and len(key) > len("sb_secret_")
    if not backend_key:
        try:
            payload = key.split(".")[1]
            role = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))).get("role")
            backend_key = role == "service_role"
        except (ValueError, IndexError, TypeError, AttributeError):
            backend_key = False
    if not backend_key or any(char.isspace() for char in key):
        raise DatabaseConfigurationError(
            "SUPABASE_SECRET_KEY must be a backend secret or legacy service_role key."
        )
    return url, key


def rpc(name: str, params: dict | None = None):
    """Execute one Data API RPC and close its HTTP transport, without retries.

    A write RPC may have committed if its response is lost. Never automatically
    retry receipt creation, because that could create duplicate receipts.
    """
    url, key = _configuration()
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=False) as transport:
            client = create_client(url, key, options=ClientOptions(
                httpx_client=transport, postgrest_client_timeout=REQUEST_TIMEOUT_SECONDS,
                auto_refresh_token=False, persist_session=False,
            ))
            data = client.rpc(name, params or {}).execute().data
    except APIError as exc:
        if str(exc.code) in {"23502", "23503", "23505", "23514", "22003", "22007", "22P02", "22023"}:
            raise DatabaseConstraintError("Database constraints rejected the supplied data.", str(exc.code)) from None
        if str(exc.code) in {"PGRST202", "PGRST204", "42P01", "42883", "3F000"}:
            raise DatabaseError("Supabase schema is not ready. Run schema.sql in the Supabase SQL Editor.") from None
        if str(exc.code) in {"42501", "PGRST301", "PGRST302", "PGRST303"}:
            raise DatabaseError("Supabase rejected backend access. Check the secret key and schema grants.") from None
        raise DatabaseError("Supabase could not complete the database request.") from None
    except httpx.TimeoutException:
        raise DatabaseError("Supabase HTTPS request timed out. Please try again after checking the service.") from None
    except httpx.HTTPError:
        raise DatabaseError("Supabase HTTPS request failed. Check service availability and network access.") from None
    except (ValueError, AttributeError, TypeError):
        raise DatabaseError("Supabase returned an invalid response or client configuration.") from None
    if data is not None and not isinstance(data, (dict, list)):
        raise DatabaseError("Supabase returned an invalid database response.")
    return data


def check_connection() -> dict:
    result = rpc("ripple_check")
    if not isinstance(result, dict) or result.get("status") != "ok" or result.get("schema_version") != 2:
        raise DatabaseError("Supabase schema check failed. Run the current schema.sql in the SQL Editor.")
    return result
