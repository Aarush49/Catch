"""Compatibility command: SQL installation is manual; this only verifies HTTPS."""

from app.database import DatabaseError, check_connection


def main() -> int:
    try:
        check_connection()
    except DatabaseError as exc:
        print(f"Database verification failed: {exc}")
        print("Install schema.sql in your Supabase project's SQL Editor, then retry.")
        return 1
    print("Supabase HTTPS connection and Ripple schema verified. No schema changes were executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
