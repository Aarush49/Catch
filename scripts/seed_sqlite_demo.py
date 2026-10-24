"""Create a repeatable local demo account and sample financial history.

Run from the repository root: python scripts/seed_sqlite_demo.py
Demo credentials: demo@ripple.local / RippleDemo123!
"""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.services import sqlite_store


sqlite_store.init_db()
email = "demo@ripple.local"
password = "RippleDemo123!"
with sqlite_store.connect() as conn:
    user = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
if user is None:
    user_id = sqlite_store.create_user(email, password)["id"]
else:
    user_id = user["id"]

examples = [
    ("sample-grocery", "purchase", "68.42", date.today() - timedelta(days=2), "Neighborhood Market", "groceries"),
    ("sample-coffee", "purchase", "5.75", date.today() - timedelta(days=1), "Coffee Shop", "restaurant"),
    ("sample-salary", "income", "2450.00", date.today() - timedelta(days=3), "Salary payroll deposit", "salary"),
    ("sample-rent", "withdrawal", "950.00", date.today() - timedelta(days=5), "Rent payment", "housing"),
]
rows = [{"id": key, "source": "demo", "type": kind, "amount": amount, "date": when, "description": description, "category": category, "raw": {"demo": True}} for key, kind, amount, when, description, category in examples]
sqlite_store.upsert_transactions(user_id, rows)
print(f"Demo account ready: {email} / {password}")
print(f"SQLite database: {sqlite_store.database_path()}")
print("Sample purchase, salary deposit, and withdrawal rows are ready.")
