from fastapi import APIRouter, HTTPException, Request

from ..auth import create_token, login_limiter, verify_login
from ..schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request) -> TokenResponse:
    ip = request.client.host if request.client else "unknown"
    if login_limiter.locked(ip):
        raise HTTPException(
            status_code=429, detail="Too many failed login attempts — try again later"
        )
    if not verify_login(body.email, body.password):
        login_limiter.record_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    login_limiter.record_success(ip)
    return TokenResponse(token=create_token(body.email))
