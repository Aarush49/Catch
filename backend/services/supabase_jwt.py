import os
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database import DatabaseConfigurationError, supabase_url

bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=600, timeout=10)


def _decode(token: str) -> dict[str, Any]:
    base = supabase_url()
    options = {"require": ["exp", "sub"]}
    secret = os.getenv("SUPABASE_JWT_SECRET", "").strip()
    if secret:
        return jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated",
                          issuer=f"{base}/auth/v1", options=options)
    jwks_url = os.getenv("SUPABASE_JWKS_URL", "").strip() or f"{base}/auth/v1/.well-known/jwks.json"
    key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
    return jwt.decode(token, key.key, algorithms=["RS256", "ES256"], audience="authenticated",
                      issuer=f"{base}/auth/v1", options=options)


def require_supabase_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=401, detail="A valid Supabase session is required.",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = _decode(credentials.credentials)
    except DatabaseConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(status_code=503, detail="Could not reach Supabase to verify the session.") from None
    except Exception:
        raise HTTPException(status_code=401, detail="The Supabase session is invalid or expired.",
                            headers={"WWW-Authenticate": "Bearer"}) from None
    return payload


def current_user(payload: Annotated[dict[str, Any], Depends(require_supabase_user)]) -> dict[str, Any]:
    return {"id": payload["sub"], "email": payload.get("email")}
