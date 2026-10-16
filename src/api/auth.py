import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from src.services.auth_service import register_user, login_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr
    password: str = Field(min_length=1)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest):
    try:
        result = register_user(
            request.username,
            str(request.email),
            request.password,
        )
        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    except Exception:
        logger.exception("Registration endpoint failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to an internal error.",
        )


@router.post("/login")
def login(request: LoginRequest):
    try:
        result = login_user(
            request.username,
            request.password,
        )
        return result

    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        ) from exc

    except Exception:
        logger.exception("Login endpoint failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed due to an internal error. Check the server log.",
        )