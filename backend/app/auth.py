import hmac
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

bearer = HTTPBearer(auto_error=False)


def create_token(email: str) -> str:
    settings = get_settings()
    payload = {
        "sub": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_ttl_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def verify_login(email: str, password: str) -> bool:
    settings = get_settings()
    return hmac.compare_digest(email, settings.admin_email) and hmac.compare_digest(
        password, settings.admin_password
    )


def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(
            credentials.credentials, get_settings().jwt_secret, algorithms=["HS256"]
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload["sub"]
