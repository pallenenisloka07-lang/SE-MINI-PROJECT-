import logging

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Response,
    status,
)
from jose import jwt
from pydantic import BaseModel, EmailStr, Field

from src.services.auth_service import (
    register_user,
    login_user,
    logout_user,
)
from src.repositories.admin_repository import record_audit_event

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


def record_audit_safely(user_id, username, action, details):
    """Audit events must never expose passwords or access tokens."""
    try:
        record_audit_event(
            user_id=user_id,
            username=username,
            action=action,
            details=details,
        )
    except Exception:
        logger.exception("Failed to record audit event: %s", action)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr
    password: str = Field(min_length=1)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
)
def register(request: RegisterRequest):
    try:
        return register_user(
            request.username,
            str(request.email),
            request.password,
        )

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

    except Exception as exc:
        logger.exception("Registration endpoint failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to an internal error.",
        ) from exc


@router.post("/login")
def login(request: LoginRequest):
    try:
        result = login_user(
            request.username,
            request.password,
        )

        # This token was just issued by our own login service.
        claims = jwt.get_unverified_claims(result["access_token"])

        try:
            user_id = int(claims["sub"])
        except (KeyError, TypeError, ValueError):
            user_id = None

        record_audit_safely(
            user_id,
            claims.get("username", request.username),
            "login_success",
            "Login succeeded",
        )

        return result

    except PermissionError as exc:
        record_audit_safely(
            None,
            request.username[:100],
            "login_failure",
            "Login rejected: invalid credentials",
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        ) from exc

    except Exception as exc:
        logger.exception("Login endpoint failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed due to an internal error.",
        ) from exc


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    authorization: str | None = Header(default=None),
):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
        )

    scheme, separator, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not separator or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    # Obtain claims for audit identification. The logout service must
    # still validate the token before a successful logout is recorded.
    try:
        claims = jwt.get_unverified_claims(token)
    except Exception:
        claims = {}

    try:
        logout_user(token)

    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
        ) from exc

    try:
        user_id = int(claims["sub"])
    except (KeyError, TypeError, ValueError):
        user_id = None

    record_audit_safely(
        user_id,
        claims.get("username"),
        "logout",
        "Logout succeeded",
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)