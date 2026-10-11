import os
import time
import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY and os.getenv("ENVIRONMENT") == "production":
    raise RuntimeError("JWT_SECRET must be set in production.")
SECRET_KEY = SECRET_KEY or "dev-only-secret-change-before-deployment"
TOKEN_LIFETIME_SECONDS = 30 * 60

# Demo account for the capstone. Replace with a database-backed identity provider in production.
USERS = {
    "mercy": {
        "password_hash": bcrypt.hashpw(
            os.getenv("DEMO_PASSWORD", "logistics2026").encode(), bcrypt.gensalt()
        ),
        "role": "coordinator",
    },
    "worker": {
        "password_hash": bcrypt.hashpw(
            os.getenv("WORKER_PASSWORD", "worker2026").encode(), bcrypt.gensalt()
        ),
        "role": "health_worker",
    },
}

def check_password(username: str, password: str) -> bool:
    user = USERS.get(username)
    return bool(user and bcrypt.checkpw(password.encode(), user["password_hash"]))

def create_token(username: str) -> str:
    user = USERS.get(username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    now = int(time.time())
    return jwt.encode(
        {"sub": username, "role": user["role"], "iat": now,
         "exp": now + TOKEN_LIFETIME_SECONDS},
        SECRET_KEY, algorithm="HS256"
    )

bearer = HTTPBearer(auto_error=False)

def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Bearer token required.")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired. Log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")
    if not payload.get("sub") or not payload.get("role"):
        raise HTTPException(status_code=401, detail="Token is missing required claims.")
    return payload
