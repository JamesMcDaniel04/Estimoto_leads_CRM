import hmac
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings

bearer = HTTPBearer(auto_error=False)


class LoginRateLimiter:
    """Sliding-window lockout on failed logins, keyed by client IP.

    In-memory on purpose: the app runs as a single process (SQLite, one Fly
    machine), and the admin password is the only credential in the system —
    this is brute-force protection, not distributed rate limiting.
    """

    def __init__(self, max_failures: int = 5, window_seconds: int = 300):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, ip: str) -> None:
        cutoff = time.monotonic() - self.window_seconds
        failures = self._failures[ip]
        while failures and failures[0] < cutoff:
            failures.popleft()

    def locked(self, ip: str) -> bool:
        self._prune(ip)
        return len(self._failures[ip]) >= self.max_failures

    def record_failure(self, ip: str) -> None:
        self._prune(ip)
        self._failures[ip].append(time.monotonic())

    def record_success(self, ip: str) -> None:
        self._failures.pop(ip, None)

    def reset(self) -> None:
        self._failures.clear()


login_limiter = LoginRateLimiter()


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
