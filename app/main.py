import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Resolve the project-root .env from this file instead of depending on the
# directory Uvicorn was launched from.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.database import DatabaseError
from backend.routers import nessie, predictions, shopping, shopping_list, spending
from backend.services.receipt_scanner import OCRConfigurationError, scan_image
from backend.services.supabase_jwt import require_supabase_user

app = FastAPI(title="Ripple API", description="Receipt scanning, shopping comparison, and banking API")
allowed_origins = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024


@app.exception_handler(DatabaseError)
async def database_error_handler(_request, exc: DatabaseError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/receipts/scan")
def scan_receipt(file: UploadFile = File(...), _user=Depends(require_supabase_user)) -> dict[str, Any]:
    """Read a receipt with OCR and local parsing. Nothing is saved until reviewed."""
    mime_type = (file.content_type or "").lower()
    if mime_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="Upload a JPEG, PNG, WebP, or HEIC image.")
    image_bytes = file.file.read(MAX_IMAGE_BYTES + 1)
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 8 MB or smaller.")
    try:
        return scan_image(image_bytes, mime_type)
    except OCRConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except Exception as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from None


for api_router in (nessie.router, predictions.router, shopping.router, shopping_list.router, spending.router):
    app.include_router(api_router)
