"""Manually create/reuse a demo account and upsert sample history in Supabase.

Run from the repository root: python -m scripts.seed_supabase_demo
Default demo login: demo@ripple.local / RippleDemo123!
Override with RIPPLE_DEMO_EMAIL and RIPPLE_DEMO_PASSWORD for a private demo.
"""

import os
from datetime import date, timedelta

from app.database import DatabaseError
from backend.services import supabase_store as store


def main() -> int:
    email = os.getenv("RIPPLE_DEMO_EMAIL", "demo@ripple.local")
    password = os.getenv("RIPPLE_DEMO_PASSWORD", "RippleDemo123!")
    try:
        user = store.authenticate(email, password)
        if user is None:
            try:
                user = store.create_user(email, password)
            except ValueError:
                print("The demo email already exists with a different password. Set RIPPLE_DEMO_PASSWORD to its password.")
                return 1
        examples = [
            ("sample-grocery", "purchase", "68.42", 2, "Neighborhood Market", "groceries"),
            ("sample-coffee", "purchase", "5.75", 1, "Coffee Shop", "restaurant"),
            ("sample-salary", "income", "2450.00", 3, "Salary payroll deposit", "salary"),
            ("sample-rent", "withdrawal", "950.00", 5, "Rent payment", "housing"),
        ]
        rows = [{
            "id": key, "source": "demo", "type": kind, "amount": amount,
            "date": date.today() - timedelta(days=days), "description": description,
            "category": category, "raw": {"demo": True},
        } for key, kind, amount, days, description, category in examples]
        count = store.upsert_transactions(user["id"], rows)
    except DatabaseError as exc:
        print(f"Supabase demo setup failed: {exc}")
        return 1
    print(f"Supabase demo account ready; {count} sample transactions upserted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
