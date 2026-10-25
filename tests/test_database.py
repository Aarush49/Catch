import base64
import json

import httpx
import pytest

from app import database
from scripts import init_db


def test_real_sdk_uses_https_rpc_and_closes_transport(supabase_mock):
    assert database.check_connection() == {"status": "ok", "schema_version": 2}
    assert supabase_mock.calls == [("ripple_check", {})]
    assert all(client.is_closed for client in supabase_mock.transports)
    assert supabase_mock.transports[0].timeout.read == 15


@pytest.mark.parametrize("variable", ["SUPABASE_URL", "SUPABASE_SECRET_KEY"])
def test_missing_configuration_is_safe(monkeypatch, supabase_mock, variable):
    monkeypatch.delenv(variable)
    with pytest.raises(database.DatabaseConfigurationError):
        database.check_connection()
    assert not supabase_mock.calls


@pytest.mark.parametrize("url", [
    "not-a-url", "postgresql://user:password@host/db", "http://ripple-test.supabase.co",
    "https://user:password@ripple-test.supabase.co", "https://ripple-test.supabase.co/rest/v1",
    "https://ripple-test.supabase.co?secret=password", "https://ripple-test.supabase.co:5432",
])
def test_invalid_project_url(monkeypatch, supabase_mock, url):
    monkeypatch.setenv("SUPABASE_URL", url)
    with pytest.raises(database.DatabaseConfigurationError) as error:
        database.check_connection()
    assert "password" not in str(error.value)
    assert not supabase_mock.calls


@pytest.mark.parametrize("key", ["", "sb_publishable_not_for_backend", "anon-key", "sb_secret_", "sb_secret_bad key"])
def test_rejects_missing_or_public_credentials(monkeypatch, supabase_mock, key):
    monkeypatch.setenv("SUPABASE_SECRET_KEY", key)
    with pytest.raises(database.DatabaseConfigurationError):
        database.check_connection()
    assert not supabase_mock.calls


@pytest.mark.parametrize("role, allowed", [("anon", False), ("authenticated", False), ("service_role", True)])
def test_legacy_jwt_role_is_checked(monkeypatch, role, allowed):
    payload = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode().rstrip("=")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", f"header.{payload}.signature")
    if allowed:
        assert database._configuration()[1].startswith("header.")
    else:
        with pytest.raises(database.DatabaseConfigurationError):
            database._configuration()


@pytest.mark.parametrize("code, expected", [
    ("23503", database.DatabaseConstraintError), ("23514", database.DatabaseConstraintError),
    ("PGRST202", database.DatabaseError), ("42P01", database.DatabaseError),
    ("42501", database.DatabaseError), ("PGRST301", database.DatabaseError), ("XX000", database.DatabaseError),
])
def test_provider_errors_are_redacted(supabase_mock, code, expected):
    supabase_mock.status = 400
    supabase_mock.responses["ripple_check"] = {
        "code": code, "message": "sb_secret_test_key_never_real", "details": "private-host", "hint": "private data",
    }
    with pytest.raises(expected) as error:
        database.check_connection()
    assert "sb_secret_test_key_never_real" not in str(error.value)
    assert "private-host" not in str(error.value)
    assert all(client.is_closed for client in supabase_mock.transports)


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("sb_secret_test_key_never_real"), httpx.ConnectError("sb_secret_test_key_never_real")])
def test_transport_errors_are_redacted_and_not_retried(supabase_mock, failure):
    supabase_mock.failure = failure
    with pytest.raises(database.DatabaseError) as error:
        database.check_connection()
    assert "sb_secret_test_key_never_real" not in str(error.value)
    assert len(supabase_mock.calls) == 1
    assert all(client.is_closed for client in supabase_mock.transports)


@pytest.mark.parametrize("response", [None, [], {"status": "bad"}, {"status": "ok", "schema_version": 0}])
def test_schema_check_rejects_invalid_response(supabase_mock, response):
    supabase_mock.responses["ripple_check"] = response
    with pytest.raises(database.DatabaseError):
        database.check_connection()


def test_verification_command_is_read_only(supabase_mock, capsys):
    assert init_db.main() == 0
    assert supabase_mock.calls == [("ripple_check", {})]
    assert "No schema changes were executed" in capsys.readouterr().out


def test_verification_failure_exit_code(monkeypatch, capsys):
    monkeypatch.delenv("SUPABASE_URL")
    assert init_db.main() == 1
    assert "SQL Editor" in capsys.readouterr().out
