from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database.connection import get_db
from backend.app.models.models import Category, Document, User
from backend.app.storage.file_storage import (
    MAX_FILE_SIZE,
    delete_file,
    get_file,
    save_file,
)
from src.api.dependencies import get_current_user

router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
    dependencies=[],
)


def document_owner(db: Session, account: dict) -> User:
    """Map an authenticated account to its document-database user by email."""
    owner = (
        db.query(User)
        .filter(User.email == account["email"])
        .first()
    )
    if owner:
        return owner

    username = account["username"]
    if db.query(User).filter(User.username == username).first():
        username = f"{username}_{account['id']}"

    role = "admin" if account["role"].lower() == "admin" else "user"
    owner = User(
        username=username,
        email=account["email"],
        password_hash="managed-by-authentication-database",
        role=role,
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


def owned_document(db: Session, doc_id: int, owner_id: int) -> Document:
    document = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.owner_id == owner_id)
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def document_json(document: Document) -> dict:
    return {
        "id": document.id,
        "title": document.title,
        "original_filename": document.original_filename,
        "file_type": document.file_type,
        "file_size": document.file_size,
        "category_id": document.category_id,
        "status": document.status,
        "upload_date": document.upload_date.isoformat() if document.upload_date else None,
        "extracted_text": document.extracted_text,
    }


class DocumentUpdate(BaseModel):
    title: str | None = None
    category_id: int | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    category_id: int | None = Form(default=None),
    account: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filename = Path(file.filename or "").name
    if not filename:
        raise HTTPException(status_code=400, detail="A filename is required")

    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds the 10 MB upload limit")

    owner = document_owner(db, account)
    if category_id is not None and db.get(Category, category_id) is None:
        raise HTTPException(status_code=400, detail="Category not found")

    try:
        storage_path = save_file(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        document = Document(
            owner_id=owner.id,
            category_id=category_id,
            title=(title or Path(filename).stem).strip()[:255],
            original_filename=filename[:255],
            file_type=Path(filename).suffix.lower(),
            file_size=len(content),
            storage_path=storage_path,
            status="Uploaded",
        )
        if not document.title:
            raise HTTPException(status_code=400, detail="Title cannot be empty")

        db.add(document)
        db.commit()
        db.refresh(document)
        return document_json(document)
    except Exception:
        db.rollback()
        delete_file(storage_path)
        raise
    finally:
        await file.close()


@router.get("")
def list_documents(
    account: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner = document_owner(db, account)
    documents = (
        db.query(Document)
        .filter(Document.owner_id == owner.id)
        .order_by(Document.upload_date.desc())
        .all()
    )
    return [document_json(document) for document in documents]


@router.get("/{doc_id}")
def get_document(
    doc_id: int,
    account: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner = document_owner(db, account)
    return document_json(owned_document(db, doc_id, owner.id))


@router.get("/{doc_id}/download")
def download_document(
    doc_id: int,
    account: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner = document_owner(db, account)
    document = owned_document(db, doc_id, owner.id)
    try:
        path = get_file(document.storage_path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail="Stored file not found") from exc

    return FileResponse(
        path=path,
        filename=document.original_filename,
        media_type="application/octet-stream",
    )


@router.patch("/{doc_id}")
def update_document(
    doc_id: int,
    update: DocumentUpdate,
    account: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner = document_owner(db, account)
    document = owned_document(db, doc_id, owner.id)
    changes = update.model_dump(exclude_unset=True)

    if "title" in changes:
        title = changes["title"]
        if title is None or not title.strip():
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        document.title = title.strip()[:255]

    if "category_id" in changes:
        category_id = changes["category_id"]
        if category_id is not None and db.get(Category, category_id) is None:
            raise HTTPException(status_code=400, detail="Category not found")
        document.category_id = category_id
        document.category_source = "manual"

    db.commit()
    db.refresh(document)
    return document_json(document)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    doc_id: int,
    account: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner = document_owner(db, account)
    document = owned_document(db, doc_id, owner.id)
    storage_path = document.storage_path

    db.delete(document)
    db.commit()
    delete_file(storage_path)
    return None
