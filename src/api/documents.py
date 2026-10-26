
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
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
from src.repositories.admin_repository import record_audit_event
from src.repositories.document_repository import save_analysis_results
from src.services.document_service import (
    upload_document as service_upload_document,
    process_document,
    list_user_documents,
    get_user_document,
    queue_reprocessing,
)

router = APIRouter(prefix="/api/documents", tags=["Documents"])


def account_identity_id(account: dict) -> int:
    value = account.get("id")
    if value is None:
        value = account.get("sub")
    if value is None:
        value = account.get("user_id")

    if value is None:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user ID is missing",
        )

    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user ID is invalid",
        ) from exc


def document_owner(db: Session, account: dict) -> User:
    account_id = account_identity_id(account)
    username = str(account.get("username") or f"user_{account_id}")
    raw_email = account.get("email")
    email = str(raw_email).strip().lower() if raw_email else None

    # Use email when authentication provides it.
    if email:
        owner = db.query(User).filter(User.email == email).first()
        if owner:
            return owner
    else:
        # Some authentication tokens contain username and ID, but no email.
        # Reuse the existing local document owner when possible.
        owner = db.query(User).filter(User.username == username).first()
        if owner:
            return owner

        # Supply a stable fallback address for the local database record.
        email = f"user_{account_id}@local.invalid"

    existing_username = (
        db.query(User).filter(User.username == username).first()
    )
    if existing_username:
        username = f"{username}_{account_id}"

    existing_email = db.query(User).filter(User.email == email).first()
    if existing_email:
        return existing_email

    role = (
        "admin"
        if str(account.get("role", "")).lower()
        in {"admin", "administrator"}
        else "user"
    )
    owner = User(
        username=username,
        email=email,
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
        .filter(
            Document.id == doc_id,
            Document.owner_id == owner_id,
        )
        .first()
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def document_json(document: Document) -> dict:
    category_obj = getattr(document, "category", None)
    category_name = (
        getattr(category_obj, "name", None)
        if category_obj is not None
        else None
    )

    return {
        "id": document.id,
        "title": document.title,
        "original_filename": document.original_filename,
        "file_type": document.file_type,
        "file_size": document.file_size,
        "category_id": document.category_id,
        "category": category_name,
        "status": document.status,
        "processing_status": getattr(
            document, "processing_status", document.status
        ),
        "keywords": [],
        "topics": [],
        "upload_date": (
            document.upload_date.isoformat()
            if document.upload_date
            else None
        ),
        "extracted_text": document.extracted_text,
    }


def find_service_document(account: dict, document: Document) -> dict | None:
    service_result = list_user_documents(account_identity_id(account))
    matches = [
        item
        for item in service_result["items"]
        if item.get("original_filename") == document.original_filename
        and item.get("title") == document.title
    ]
    if not matches:
        return None

    return max(matches, key=lambda item: item.get("created_at") or "")


def add_service_metadata(
    result: dict,
    account: dict,
    service_doc: dict | None,
) -> dict:
    if not service_doc:
        return result

    try:
        details = get_user_document(account_identity_id(account), service_doc["id"])
    except FileNotFoundError:
        return result

    result["processing_status"] = details.get(
        "processing_status", result["processing_status"]
    )
    result["keywords"] = details.get("keywords", [])
    result["topics"] = details.get("topics", [])
    result["extracted_text"] = details.get(
        "extracted_text", result.get("extracted_text")
    )
    return result


class DocumentUpdate(BaseModel):
    title: str | None = None
    category_id: int | None = None
    category: str | None = None


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
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File exceeds the 10 MB upload limit",
        )
    if title is not None and not title.strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    if category_id is not None and db.get(Category, category_id) is None:
        raise HTTPException(status_code=400, detail="Category not found")

    try:
        storage_path = save_file(content, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        await file.close()

    try:
        owner = document_owner(db, account)
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
        db.add(document)
        db.commit()
        db.refresh(document)

        service_doc = service_upload_document(
            owner_id=account_identity_id(account),
            filename=filename,
            content=content,
            title=document.title,
        )

        process_document(
            document_id=service_doc["id"],
            owner_id=account_identity_id(account),
            index_document_id=document.id,
        )

        record_audit_event(
            user_id=account_identity_id(account),
            username=account.get("username", ""),
            action="document_upload",
            details=f"Document {document.id} uploaded",
        )

        return add_service_metadata(
            document_json(document),
            account,
            service_doc,
        )
    except Exception:
        db.rollback()
        delete_file(storage_path)
        raise


@router.get("")
def list_documents(
    page: int = 1,
    limit: int = 20,
    account: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be at least 1")
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100",
        )

    owner = document_owner(db, account)
    query = db.query(Document).filter(Document.owner_id == owner.id)
    total = query.count()
    documents = (
        query.order_by(Document.upload_date.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    service_result = list_user_documents(account_identity_id(account))
    service_by_key = {}
    for item in service_result["items"]:
        key = (item.get("original_filename"), item.get("title"))
        service_by_key.setdefault(key, []).append(item)

    results = []
    for document in documents:
        key = (document.original_filename, document.title)
        candidates = service_by_key.get(key, [])
        service_doc = candidates.pop(0) if candidates else None
        results.append(
            add_service_metadata(
                document_json(document),
                account,
                service_doc,
            )
        )

    return {
        "items": results,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
    }


@router.post("/{doc_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
def reprocess_document(
    doc_id: int,
    account: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner = document_owner(db, account)
    document = owned_document(db, doc_id, owner.id)
    service_doc = find_service_document(account, document)

    if service_doc is None:
        raise HTTPException(
            status_code=404,
            detail="Document processing record not found",
        )

    try:
        queue_reprocessing(
            owner_id=account_identity_id(account),
            document_id=service_doc["id"],
            index_document_id=document.id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    process_document(
        document_id=service_doc["id"],
        owner_id=account_identity_id(account),
        index_document_id=document.id,
    )

    return {
        "message": "Document reprocessing completed",
        "document_id": document.id,
    }


@router.get("/{doc_id}")
def get_document(
    doc_id: int,
    account: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owner = document_owner(db, account)
    document = owned_document(db, doc_id, owner.id)
    service_doc = find_service_document(account, document)
    return add_service_metadata(
        document_json(document),
        account,
        service_doc,
    )


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
        raise HTTPException(
            status_code=404,
            detail="Stored file not found",
        ) from exc

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
            raise HTTPException(
                status_code=400,
                detail="Title cannot be empty",
            )
        document.title = title.strip()[:255]

    if "category_id" in changes:
        category_id = changes["category_id"]
        if category_id is not None and db.get(Category, category_id) is None:
            raise HTTPException(status_code=400, detail="Category not found")
        document.category_id = category_id
        document.category_source = "manual"

    if "category" in changes:
        category_name = changes["category"]
        if category_name is None or not category_name.strip():
            raise HTTPException(
                status_code=400,
                detail="Category cannot be empty",
            )

        category_name = category_name.strip()
        category_obj = (
            db.query(Category)
            .filter(Category.name.ilike(category_name))
            .first()
        )

        if category_obj is None:
            category_obj = Category(
                name=category_name,
                description=f"Category: {category_name}",
            )
            db.add(category_obj)
            db.flush()

        document.category_id = category_obj.id
        document.category_source = "manual"

    db.commit()
    db.refresh(document)

    # Keep the service-side search record in sync with manual category changes.
    if "category" in changes:
        service_doc = find_service_document(account, document)
        if service_doc is not None:
            service_details = get_user_document(
                account_identity_id(account), service_doc["id"]
            )
            save_analysis_results(
                document_id=service_doc["id"],
                owner_id=account_identity_id(account),
                category=changes["category"].strip(),
                confidence=float(
                    service_details.get(
                        "confidence",
                        service_doc.get("confidence", 1.0),
                    ) or 1.0
                ),
                keywords=service_details.get("keywords", []),
                topics=service_details.get("topics", []),
            )

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
    document_id = document.id

    db.delete(document)
    db.commit()
    delete_file(storage_path)

    record_audit_event(
        user_id=account_identity_id(account),
        username=account.get("username", ""),
        action="document_delete",
        details=f"Document {document_id} deleted",
    )
    return None
