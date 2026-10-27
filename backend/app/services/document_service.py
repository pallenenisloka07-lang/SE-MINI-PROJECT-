
from sqlalchemy.orm import Session

from backend.app.models.models import Category, Document
from backend.app.storage.file_storage import delete_file, get_file


def update_document(
    db: Session,
    document_id: int,
    owner_id: int,
    title: str | None = None,
    category_id: int | None = None,
) -> Document | None:
    """Update a document owned by the specified user."""
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

    if title is not None:
        title = title.strip()
        if not title:
            raise ValueError("Document title cannot be empty.")
        document.title = title

    if category_id is not None:
        category = (
            db.query(Category)
            .filter(Category.id == category_id)
            .first()
        )

        if category is None:
            raise ValueError("Category does not exist.")

        document.category_id = category_id
        document.category_source = "manual"

    try:
        db.commit()
        db.refresh(document)
        return document
    except Exception:
        db.rollback()
        raise


def delete_document(
    db: Session,
    document_id: int,
    owner_id: int,
) -> bool:
    """
    Delete an owned document and its stored file.

    Returns False if the document is missing or belongs to another user.
    Raises an exception if deletion fails.
    """
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.owner_id == owner_id,
        )
        .first()
    )

    if document is None:
        return False

    storage_path = document.storage_path
    file_path = None
    file_bytes = None

    # Validate the path and preserve the original file for recovery.
    if storage_path:
        try:
            file_path = get_file(storage_path)
            file_bytes = file_path.read_bytes()
        except FileNotFoundError:
            file_path = None

    # Delete the physical file first.
    # If this fails, the database record remains untouched.
    if file_path is not None:
        if not delete_file(storage_path):
            raise OSError("Could not delete the document file.")

    try:
        db.delete(document)
        db.commit()
    except Exception:
        db.rollback()

        # Restore the file at its original path if the DB transaction fails.
        if file_path is not None and file_bytes is not None:
            try:
                with file_path.open("xb") as restored_file:
                    restored_file.write(file_bytes)
            except Exception as recovery_error:
                raise RuntimeError(
                    "Database deletion failed, and restoring the original "
                    f"file also failed: {storage_path}"
                ) from recovery_error

        raise

    return True
