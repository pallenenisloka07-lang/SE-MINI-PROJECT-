import os

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from src.repositories.user_repository import find_user_by_username

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise HTTPException(status_code=500, detail="Authentication is not configured")

    try:
        payload = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=["HS256"],
        )
        subject = payload.get("sub")
        username = payload.get("username")

        if not subject or not username:
            raise HTTPException(status_code=401, detail="Invalid access token")

        user = find_user_by_username(username)
        if (
            user is None
            or str(user.id) != str(subject)
            or not user.is_active
        ):
            raise HTTPException(status_code=401, detail="Invalid access token")

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email.strip().lower(),
            "role": user.role,
        }

    except HTTPException:
        raise
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
