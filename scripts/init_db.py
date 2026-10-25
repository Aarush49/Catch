"""Read-only check that supabase/schema.sql is installed. Run: python -m scripts.init_db"""

from app.database import DatabaseError, check_connection


def main() -> int:
    try:
        result = check_connection()
    except DatabaseError as exc:
        print(f"Database verification failed: {exc}")
        print("Install supabase/schema.sql in your Supabase project's SQL Editor, then retry.")
        return 1
    print(f"Supabase schema version {result['schema_version']} verified "
          f"({len(result['tables'])} tables). No schema changes were executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
