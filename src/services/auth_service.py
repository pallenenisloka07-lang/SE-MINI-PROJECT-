import os
import re
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt
from jose.exceptions import JWTError
from sqlalchemy.exc import IntegrityError

from src.repositories.user_repository import (
    create_user,
    find_user_by_username,
    find_user_by_email,
    revoke_token,
    is_token_revoked,
)


def register_user(username, email, password):
    username = username.strip()
    email = email.strip().lower()

    if not username or len(username) > 50:
        raise ValueError(
            "Username is required and must be at most 50 characters"
        )

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("A valid email address is required")

    if (
        len(password) < 8
        or not re.search(r"[A-Za-z]", password)
        or not re.search(r"\d", password)
    ):
        raise ValueError(
            "Password must be at least 8 characters "
            "and contain a letter and a digit"
        )

    if find_user_by_username(username) or find_user_by_email(email):
        raise FileExistsError("Username or email already exists")

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")

    try:
        return create_user(username, email, password_hash)
    except IntegrityError as exc:
        raise FileExistsError(
            "Username or email already exists"
        ) from exc


def login_user(username, password):
    user = find_user_by_username(username.strip())

    if not user or not user.is_active or not bcrypt.checkpw(
        password.encode("utf-8"),
        user.password_hash.encode("utf-8"),
    ):
        raise PermissionError("Invalid username or password")

    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable is not configured"
        )

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(minutes=30),
    }

    token = jwt.encode(payload, secret, algorithm="HS256")

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 1800,
        "role": user.role,
    }


def decode_access_token(token):
    """Validate a JWT and reject tokens that have been revoked."""
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET_KEY environment variable is not configured"
        )

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
        )
    except JWTError as exc:
        raise PermissionError(
            "Invalid or expired access token"
        ) from exc

    jti = payload.get("jti")
    if not jti:
        raise PermissionError("Invalid access token")

    if is_token_revoked(jti):
        raise PermissionError("Access token has been revoked")

    return payload


def logout_user(token):
    """Revoke a valid token so it cannot be reused after logout."""
    payload = decode_access_token(token)

    jti = payload.get("jti")
    expires_at = payload.get("exp")

    if not jti or expires_at is None:
        raise PermissionError("Invalid access token")

    expiry_datetime = datetime.fromtimestamp(
        float(expires_at),
        tz=timezone.utc,
    )

    revoke_token(jti, expiry_datetime)