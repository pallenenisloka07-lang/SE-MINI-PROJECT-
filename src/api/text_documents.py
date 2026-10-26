
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db
from backend.app.models.models import User
from src.api.dependencies import get_current_user
from src.repositories.admin_repository import record_audit_event
from src.services.document_service import (
    upload_document,
    process_document,
    list_user_documents,
    get_user_document,
    delete_user_document,
    edit_user_document,
)

router = APIRouter(prefix="/api/text-documents", tags=["Text Documents"])


class TextDocumentInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=100000)


def resolve_owner(db: Session, account: dict) -> User:
    username = str(account.get("username") or "")
    user_id = account.get("id") or account.get("sub") or account.get("user_id")

    owner = None
    if username:
        owner = db.query(User).filter(User.username == username).first()

    if owner is None and user_id is not None:
        try:
            owner = db.get(User, int(user_id))
        except (TypeError, ValueError):
            pass

    if owner is None:
        raise HTTPException(status_code=401, detail="User account not found")

    return owner


def public_text_document(item: dict) -> dict:
    return {
        "id": item["id"],
        "title": item.get("title", ""),
        "content": item.get("extracted_text", ""),
    }


@router.get("")
def list_text_documents(
    account: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner = resolve_owner(db, account)
    result = list_user_documents(owner.id)
    return [public_text_document(item) for item in result["items"]]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_text_document(
    data: TextDocumentInput,
    account: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    title = data.title.strip()
    content = data.content.strip()

    if not title or not content:
        raise HTTPException(status_code=400, detail="Title and content are required")

    owner = resolve_owner(db, account)
    filename = f"{title[:180]}.txt"

    try:
        result = upload_document(
            owner_id=owner.id,
            filename=filename,
            content=content.encode("utf-8"),
            title=title,
        )
        process_document(result["id"], owner.id)
        saved = get_user_document(owner.id, result["id"])
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit_event(
        user_id=owner.id,
        username=owner.username,
        action="text_document_create",
        details=f"Text document created: {title}",
    )

    return {
        "id": saved["id"],
        "title": saved["title"],
        "content": saved.get("extracted_text", content),
    }


@router.put("/{document_id}")
def update_text_document(
    document_id: int,
    data: TextDocumentInput,
    account: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    title = data.title.strip()
    content = data.content.strip()

    if not title or not content:
        raise HTTPException(status_code=400, detail="Title and content are required")

    owner = resolve_owner(db, account)

    try:
        existing = get_user_document(owner.id, document_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    
    try:
        saved = edit_text_document(
            owner.id,
            document_id,
            title,
            content,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit_event(
        user_id=owner.id,
        username=owner.username,
        action="text_document_update",
        details=f"Text document updated: {title}",
    )

    return {
        "id": saved["id"],
        "title": saved["title"],
        "content": saved.get("extracted_text", content),
    }



@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_text_document(
    document_id: int,
    account: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner = resolve_owner(db, account)

    try:
        get_user_document(owner.id, document_id)
        delete_user_document(owner.id, document_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc

    record_audit_event(
        user_id=owner.id,
        username=owner.username,
        action="text_document_delete",
        details=f"Text document deleted: {document_id}",
    )
    return None
