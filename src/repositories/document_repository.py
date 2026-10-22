from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Session

from src.repositories.user_repository import Base, SessionLocal


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(1024), nullable=False)
    file_type = Column(String(10), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    category = Column(String(100), nullable=True)
    processing_status = Column(
        String(30),
        nullable=False,
        default="Pending",
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


def _document_dict(document):
    return {
        "id": document.id,
        "owner_id": document.owner_id,
        "title": document.title,
        "original_filename": document.original_filename,
        "storage_path": document.storage_path,
        "file_type": document.file_type,
        "size_bytes": document.size_bytes,
        "category": document.category,
        "processing_status": document.processing_status,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def create_document(
    owner_id,
    title,
    original_filename,
    storage_path,
    file_type,
    size_bytes,
):
    with SessionLocal() as db:
        document = Document(
            owner_id=owner_id,
            title=title,
            original_filename=original_filename,
            storage_path=storage_path,
            file_type=file_type,
            size_bytes=size_bytes,
            processing_status="Pending",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return _document_dict(document)


def list_documents(owner_id, offset=0, limit=20):
    with SessionLocal() as db:
        query = db.query(Document).filter(
            Document.owner_id == owner_id
        )
        total = query.count()
        documents = (
            query.order_by(Document.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [_document_dict(d) for d in documents], total


def get_document(document_id, owner_id):
    with SessionLocal() as db:
        document = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.owner_id == owner_id,
            )
            .first()
        )
        return _document_dict(document) if document else None


def update_document(document_id, owner_id, updates):
    with SessionLocal() as db:
        document = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.owner_id == owner_id,
            )
            .first()
        )
        if document is None:
            return None

        for key in ("title", "category"):
            if key in updates:
                setattr(document, key, updates[key])

        document.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(document)
        return _document_dict(document)


def delete_document(document_id, owner_id):
    with SessionLocal() as db:
        document = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.owner_id == owner_id,
            )
            .first()
        )
        if document is None:
            return None

        result = _document_dict(document)
        db.delete(document)
        db.commit()
        return result