from unittest.mock import Mock

from app.database import DatabaseError
from scripts import seed_supabase_demo


def test_demo_seed_reuses_existing_account_and_upserts(monkeypatch, capsys):
    store = seed_supabase_demo.store
    monkeypatch.setattr(store, "authenticate", Mock(return_value={"id": "demo-id"}))
    create = Mock()
    monkeypatch.setattr(store, "create_user", create)
    upsert = Mock(return_value=4)
    monkeypatch.setattr(store, "upsert_transactions", upsert)
    assert seed_supabase_demo.main() == 0
    create.assert_not_called()
    owner, rows = upsert.call_args.args
    assert owner == "demo-id"
    assert len(rows) == 4
    assert {row["source"] for row in rows} == {"demo"}
    assert "RippleDemo123!" not in capsys.readouterr().out


def test_demo_seed_does_not_reset_an_existing_password(monkeypatch):
    store = seed_supabase_demo.store
    monkeypatch.setattr(store, "authenticate", Mock(return_value=None))
    monkeypatch.setattr(store, "create_user", Mock(side_effect=ValueError("Already exists")))
    upsert = Mock()
    monkeypatch.setattr(store, "upsert_transactions", upsert)
    assert seed_supabase_demo.main() == 1
    upsert.assert_not_called()


def test_demo_seed_handles_database_unavailability(monkeypatch, capsys):
    monkeypatch.setattr(seed_supabase_demo.store, "authenticate", Mock(side_effect=DatabaseError("Supabase unavailable")))
    assert seed_supabase_demo.main() == 1
    assert "Supabase unavailable" in capsys.readouterr().out
