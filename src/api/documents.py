
import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from src.document_manager import DocumentManager
from src.repositories.user_repository import find_user_by_username

router = APIRouter(prefix="/api/documents", tags=["Documents"])
bearer_scheme = HTTPBearer(auto_error=False)
documents = DocumentManager()


def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret is not configured",
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=["HS256"],
        )
        username = payload.get("username")
        subject = payload.get("sub")
        if not username or not subject:
            raise JWTError("Missing token claims")
        user_id = int(subject)
    except (JWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = find_user_by_username(username)
    if user is None or user.id != user_id or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is no longer active",
        )

    return {"id": user.id, "username": user.username, "role": user.role}


class DocumentInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=100000)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_document(
    body: DocumentInput,
    user: dict = Depends(current_user),
):
    try:
        doc_id = documents.add(user["id"], body.title, body.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return documents.get(user["id"], doc_id)


@router.get("")
def list_documents(
    search: str | None = Query(default=None, max_length=200),
    user: dict = Depends(current_user),
):
    if search is not None:
        return documents.search(user["id"], search)
    return documents.view_all(user["id"])


@router.get("/{doc_id}")
def get_document(doc_id: int, user: dict = Depends(current_user)):
    document = documents.get(user["id"], doc_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.put("/{doc_id}")
def update_document(
    doc_id: int,
    body: DocumentInput,
    user: dict = Depends(current_user),
):
    try:
        updated = documents.edit(
            user["id"], doc_id, body.title, body.content
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not updated:
        raise HTTPException(status_code=404, detail="Document not found")
    return documents.get(user["id"], doc_id)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: int, user: dict = Depends(current_user)):
    if not documents.delete(user["id"], doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
