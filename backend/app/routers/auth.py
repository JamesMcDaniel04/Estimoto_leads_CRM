from fastapi import APIRouter, HTTPException

from ..auth import create_token, verify_login
from ..schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    if not verify_login(body.email, body.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(token=create_token(body.email))
