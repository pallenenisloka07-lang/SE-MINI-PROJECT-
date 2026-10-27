import json
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    inspect,
)

from src.repositories.user_repository import Base, SessionLocal, engine


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
    category_confidence = Column(Float, nullable=True)
    category_is_manual = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    processing_status = Column(
        String(30),
        nullable=False,
        default="Uploaded",
    )
    extracted_text = Column(Text, nullable=True)
    processing_error = Column(Text, nullable=True)

    keywords_json = Column(Text, nullable=True)
    topics_json = Column(Text, nullable=True)

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


def migrate_document_schema():
    """Create the table if needed and add missing columns."""
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    if not inspector.has_table("documents"):
        return

    existing = {
        column["name"]
        for column in inspector.get_columns("documents")
    }

    additions = {
        "extracted_text": "TEXT",
        "processing_error": "TEXT",
        "category_confidence": "FLOAT",
        "category_is_manual": "BOOLEAN NOT NULL DEFAULT FALSE",
        "keywords_json": "TEXT",
        "topics_json": "TEXT",
    }

    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in existing:
                connection.exec_driver_sql(
                    f"ALTER TABLE documents ADD COLUMN "
                    f"{name} {definition}"
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
        "category_confidence": document.category_confidence,
        "category_is_manual": document.category_is_manual,
        "processing_status": document.processing_status,
        "extracted_text": document.extracted_text,
        "processing_error": document.processing_error,
        "keywords_json": document.keywords_json,
        "topics_json": document.topics_json,
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
            processing_status="Uploaded",
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

                if key == "category":
                    document.category_is_manual = True

        document.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(document)

        return _document_dict(document)


def _update_processing_fields(document_id, owner_id, fields):
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

        for key, value in fields.items():
            setattr(document, key, value)

        document.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(document)

        return _document_dict(document)


def mark_document_uploaded(document_id, owner_id):
    return _update_processing_fields(
        document_id,
        owner_id,
        {
            "processing_status": "Uploaded",
            "processing_error": None,
        },
    )


def mark_document_processing(document_id, owner_id):
    return _update_processing_fields(
        document_id,
        owner_id,
        {
            "processing_status": "Processing",
            "processing_error": None,
        },
    )


def mark_document_processed(document_id, owner_id, extracted_text):
    return _update_processing_fields(
        document_id,
        owner_id,
        {
            "processing_status": "Processed",
            "extracted_text": extracted_text,
            "processing_error": None,
        },
    )


def mark_document_failed(document_id, owner_id, reason):
    return _update_processing_fields(
        document_id,
        owner_id,
        {
            "processing_status": "Failed",
            "processing_error": str(reason)[:1000],
        },
    )


def save_analysis_results(
    document_id,
    owner_id,
    category,
    confidence,
    keywords,
    topics,
):
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

        # Preserve a category manually chosen by the document owner.
        if not document.category_is_manual:
            document.category = category
            document.category_confidence = confidence

        document.keywords_json = json.dumps(keywords)
        document.topics_json = json.dumps(topics)
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