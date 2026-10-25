from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from backend.services import supabase_store

router = APIRouter(prefix="/api/auth", tags=["authentication"])
bearer = HTTPBearer(auto_error=False)


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=8, max_length=256)


def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Sign in to access this data.", headers={"WWW-Authenticate": "Bearer"})
    user = supabase_store.session_user(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.", headers={"WWW-Authenticate": "Bearer"})
    return user


@router.post("/signup", status_code=201)
def signup(request: Credentials):
    try:
        user = supabase_store.create_user(str(request.email), request.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {"user": user, "access_token": supabase_store.create_session(user["id"]), "token_type": "bearer"}


@router.post("/login")
def login(request: Credentials):
    user = supabase_store.authenticate(str(request.email), request.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    return {"user": user, "access_token": supabase_store.create_session(user["id"]), "token_type": "bearer"}


@router.get("/me")
def me(user=Depends(current_user)):
    return user


@router.post("/logout", status_code=204)
def logout(credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)], user=Depends(current_user)):
    supabase_store.delete_session(credentials.credentials)
