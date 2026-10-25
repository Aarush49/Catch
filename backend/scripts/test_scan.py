"""Post one local receipt image to the authenticated scan endpoint."""
import argparse
import json
import mimetypes

import httpx

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--token", required=True, help="Supabase access token")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    mime = mimetypes.guess_type(args.image)[0] or "image/jpeg"
    with open(args.image, "rb") as image:
        response = httpx.post(f"{args.url}/receipts/scan", headers={"Authorization": f"Bearer {args.token}"}, files={"file": (args.image, image, mime)}, timeout=40)
    print(response.status_code)
    print(json.dumps(response.json(), indent=2))
    response.raise_for_status()

if __name__ == "__main__":
    main()
