import os
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)

def require_supabase_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=401, detail="A valid Supabase session is required.")
    token = credentials.credentials
    try:
        secret = os.getenv("SUPABASE_JWT_SECRET")
        jwks_url = os.getenv("SUPABASE_JWKS_URL")
        if secret:
            payload = jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
        elif jwks_url:
            key = jwt.PyJWKClient(jwks_url).get_signing_key_from_jwt(token)
            payload = jwt.decode(token, key.key, algorithms=["RS256", "ES256"], audience="authenticated")
        else:
            raise RuntimeError("SUPABASE_JWT_SECRET or SUPABASE_JWKS_URL is not configured")
        if not payload.get("sub"):
            raise jwt.InvalidTokenError("missing subject")
        return payload
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except Exception:
        raise HTTPException(status_code=401, detail="The Supabase session is invalid or expired.") from None
