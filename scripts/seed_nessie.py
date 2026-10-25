"""Seed the demo Nessie account by calling the running API."""
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
with httpx.Client(timeout=60) as client:
    setup = client.post(f"{base_url}/nessie/setup")
    setup.raise_for_status()
    seeded = client.post(f"{base_url}/nessie/seed")
    seeded.raise_for_status()
    print(seeded.json())
