"""Supabase SDK boundary: HTTPS only, backend credentials, safe public errors.

The service-role key bypasses row level security, so every query built through
``execute`` must filter by the authenticated user's ID itself.
"""

import base64
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

import httpx
from dotenv import load_dotenv
from postgrest.exceptions import APIError
from supabase import Client, create_client
from supabase.client import ClientOptions

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
REQUEST_TIMEOUT_SECONDS = 15
SCHEMA_VERSION = 3
SCHEMA_HINT = "Run supabase/schema.sql in the Supabase SQL Editor."


class DatabaseError(RuntimeError):
    """Messages from this boundary are safe for the existing API error handlers."""


class DatabaseConfigurationError(DatabaseError):
    pass


class DatabaseConstraintError(DatabaseError):
    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


def supabase_url() -> str:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    if not url:
        raise DatabaseConfigurationError("SUPABASE_URL is required.")
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
    return url


def _configuration() -> tuple[str, str]:
    key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    if not os.getenv("SUPABASE_URL", "").strip() or not key:
        raise DatabaseConfigurationError("SUPABASE_URL and SUPABASE_SECRET_KEY are required.")
    url = supabase_url()
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


def execute(build: Callable[[Client], Any]):
    """Run one Data API request and close its HTTP transport, without retries."""
    url, key = _configuration()
    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=False) as transport:
            client = create_client(url, key, options=ClientOptions(
                httpx_client=transport, postgrest_client_timeout=REQUEST_TIMEOUT_SECONDS,
                auto_refresh_token=False, persist_session=False,
            ))
            data = build(client).execute().data
    except APIError as exc:
        if str(exc.code) in {"23502", "23503", "23505", "23514", "22003", "22007", "22P02", "22023"}:
            raise DatabaseConstraintError("Database constraints rejected the supplied data.", str(exc.code)) from None
        if str(exc.code) in {"PGRST202", "PGRST204", "PGRST205", "42P01", "42703", "42883", "3F000"}:
            raise DatabaseError(f"Supabase schema is not ready. {SCHEMA_HINT}") from None
        if str(exc.code) in {"42501", "PGRST301", "PGRST302", "PGRST303"}:
            raise DatabaseError("Supabase rejected backend access. Check the secret key and schema grants.") from None
        raise DatabaseError("Supabase could not complete the database request.") from None
    except httpx.TimeoutException:
        raise DatabaseError("Supabase HTTPS request timed out. Please try again after checking the service.") from None
    except httpx.HTTPError:
        raise DatabaseError("Supabase HTTPS request failed. Check service availability and network access.") from None
    except (ValueError, AttributeError, TypeError):
        raise DatabaseError("Supabase returned an invalid response or client configuration.") from None
    if data is not None and not isinstance(data, (dict, list, int)):
        raise DatabaseError("Supabase returned an invalid database response.")
    return data


# Columns each table must expose; selecting them fails if the schema is stale.
EXPECTED_COLUMNS = {
    "profiles": "id,display_name,created_at",
    "receipts": "id,user_id,merchant,purchased_at,subtotal,tax,total,image_path,created_at",
    "receipt_items": "id,receipt_id,position,name,quantity,price,category,carbon_kg_co2e",
    "shopping_items": "id,user_id,name,completed,price,brand,category,allow_lower_quality,created_at",
    "accepted_recommendations": "id,user_id,original_name,replacement_name,savings,created_at",
    "linked_accounts": "user_id,provider,customer_id,account_id,linked_at",
    "transactions": "id,user_id,source,external_id,transaction_type,amount,date,description,category,raw_json",
}


def check_connection() -> dict:
    version = execute(lambda client: client.rpc("ripple_schema_version"))
    if version != SCHEMA_VERSION:
        raise DatabaseError(f"Supabase schema version {version!r} is not {SCHEMA_VERSION}. {SCHEMA_HINT}")
    for table, columns in EXPECTED_COLUMNS.items():
        execute(lambda client, table=table, columns=columns: client.table(table).select(columns).limit(1))
    return {"status": "ok", "schema_version": SCHEMA_VERSION, "tables": sorted(EXPECTED_COLUMNS)}
