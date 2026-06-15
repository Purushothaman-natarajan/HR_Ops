"""JWT token creation and verification helpers for role-based auth."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Header, HTTPException
from jose import JWTError, jwt

from backend.config.settings import settings

SECRET_KEY = settings.auth_secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

VALID_ROLES = ("admin", "hr", "employee")


def create_token(role: str, employee_id: str = "") -> str:
    """Create a signed JWT token embedding the user's role and optional employee_id."""
    payload = {
        "sub": role,
        "role": role,
        "employee_id": employee_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token. Returns the payload dict on success, None on failure."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_role(authorization: str = Header("")) -> dict:
    """FastAPI dependency — extracts and validates the Bearer token from the Authorization header.
    
    Returns the token payload dict with 'role' and 'employee_id' keys.
    Raises 401 if the token is missing, invalid, or expired.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.replace("Bearer ", "")
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload
