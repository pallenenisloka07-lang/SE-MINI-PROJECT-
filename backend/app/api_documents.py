import os

from jose import JWTError, jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db
from backend.app.models.models import User
from backend.app.services.document_service import (
    delete_document,
    update_document,
)
from src.repositories.user_repository import find_user_by_username


router = APIRouter(prefix="/api/documents", tags=["Documents"])
bearer_scheme = HTTPBearer()


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    category_id: int | None = None


def get_current_document_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise HTTPException(
            status_code=500,
            detail="Authentication is not configured on the server",
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=["HS256"],
        )
        subject = payload.get("sub")
        username = payload.get("username")

        if not subject or not username:
            raise HTTPException(status_code=401, detail="Invalid token")

        auth_user = find_user_by_username(username)
        if auth_user is None or str(auth_user.id) != str(subject):
            raise HTTPException(status_code=401, detail="Invalid token")

    except HTTPException:
        raise
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    email = auth_user.email.strip().lower()
    username = auth_user.username.strip()

    by_email = db.query(User).filter(User.email == email).first()
    by_username = db.query(User).filter(User.username == username).first()

    if by_email and by_username and by_email.id != by_username.id:
        raise HTTPException(
            status_code=409,
            detail="Account identity conflicts with an existing document user",
        )

    document_user = by_email or by_username

    if document_user:
        if (
            document_user.email.strip().lower() != email
            or document_user.username != username
        ):
            raise HTTPException(
                status_code=409,
                detail="Account identity conflicts with an existing document user",
            )
    else:
        document_user = User(
            username=username,
            email=email,
            password_hash="external-auth",
            role="user",
        )
        db.add(document_user)
        try:
            db.commit()
            db.refresh(document_user)
        except Exception:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Could not create the document account",
            )

    return document_user


@router.patch("/{document_id}")
def update_document_route(
    document_id: int,
    changes: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_document_user),
):
    if changes.title is None and changes.category_id is None:
        raise HTTPException(
            status_code=400,
            detail="Provide a title or category_id to update",
        )

    try:
        document = update_document(
            db=db,
            document_id=document_id,
            owner_id=current_user.id,
            title=changes.title,
            category_id=changes.category_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found or access denied",
        )

    return {
        "message": "Document updated successfully",
        "document_id": document.id,
        "title": document.title,
        "category_id": document.category_id,
        "category_source": document.category_source,
    }


@router.delete("/{document_id}")
def delete_document_route(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_document_user),
):
    try:
        deleted = delete_document(
            db=db,
            document_id=document_id,
            owner_id=current_user.id,
        )
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Document not found or access denied",
        )

    return {
        "message": "Document deleted successfully",
        "document_id": document_id,
    }
