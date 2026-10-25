"""Legacy command name: demo data is now stored in Supabase over HTTPS."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.seed_supabase_demo import main

if __name__ == "__main__":
    raise SystemExit(main())
