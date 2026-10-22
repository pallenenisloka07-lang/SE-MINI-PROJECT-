import logging
import os
import uuid
import zipfile

from io import BytesIO
from pathlib import Path

from src.repositories.document_repository import (
    create_document,
    list_documents,
    get_document,
    update_document,
    delete_document,
    mark_document_uploaded,
    mark_document_processing,
    mark_document_processed,
    mark_document_failed,
)
from src.services.text_extractor import (
    extract_text,
    TextExtractionError,
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _safe_filename(filename):
    return (filename or "").replace("\\", "/").split("/")[-1].strip()


def _validate_file(filename, content):
    filename = _safe_filename(filename)
    extension = Path(filename).suffix.lower()

    if not filename or extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Only PDF, DOCX and TXT files are supported")

    if not content:
        raise ValueError("The uploaded file is empty")

    if len(content) > MAX_FILE_SIZE:
        raise ValueError("The file must not exceed 10 MB")

    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise ValueError("The file content does not match PDF format")

    if extension == ".docx":
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise ValueError("Invalid DOCX document")
        except (zipfile.BadZipFile, OSError) as exc:
            raise ValueError("Invalid DOCX file") from exc

    if extension == ".txt":
        if b"\x00" in content:
            raise ValueError("The TXT file contains binary data")
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("The TXT file must use UTF-8 encoding") from exc

    return filename, extension


def _public_document(document):
    if document is None:
        return None

    # Do not expose the internal storage path, owner ID or extracted text.
    private_fields = {
        "storage_path",
        "owner_id",
        "extracted_text",
    }

    return {
        key: value
        for key, value in document.items()
        if key not in private_fields
    }


def upload_document(owner_id, filename, content, title=None):
    filename, extension = _validate_file(filename, content)

    selected_title = (title or "").strip() or filename

    if len(selected_title) > 255:
        raise ValueError("Title must not exceed 255 characters")

    storage_dir = Path(
        os.getenv("DOCUMENT_STORAGE_PATH", "storage")
    ).resolve()
    storage_dir.mkdir(parents=True, exist_ok=True)

    stored_path = storage_dir / f"{uuid.uuid4().hex}{extension}"

    try:
        stored_path.write_bytes(content)

        document = create_document(
            owner_id=owner_id,
            title=selected_title,
            original_filename=filename,
            storage_path=str(stored_path),
            file_type=extension.lstrip("."),
            size_bytes=len(content),
        )
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise

    return _public_document(document)


def process_document(document_id, owner_id):
    """Process a stored document after the upload response is prepared."""
    document = get_document(document_id, owner_id)

    if document is None:
        return

    try:
        mark_document_processing(document_id, owner_id)

        path = Path(document["storage_path"])
        content = path.read_bytes()

        extracted = extract_text(
            document["original_filename"],
            content,
        )

        mark_document_processed(
            document_id,
            owner_id,
            extracted,
        )

    except TextExtractionError as exc:
        mark_document_failed(document_id, owner_id, str(exc))

    except OSError:
        logger.exception("Stored document could not be read")
        mark_document_failed(
            document_id,
            owner_id,
            "The stored file could not be read. Please upload it again.",
        )

    except Exception:
        logger.exception("Unexpected document-processing failure")
        mark_document_failed(
            document_id,
            owner_id,
            "Document processing failed unexpectedly.",
        )


def list_user_documents(owner_id, offset=0, limit=20):
    documents, total = list_documents(
        owner_id,
        offset=offset,
        limit=limit,
    )

    return {
        "items": [_public_document(d) for d in documents],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def get_user_document(owner_id, document_id):
    document = get_document(document_id, owner_id)

    if document is None:
        raise FileNotFoundError("Document not found")

    return _public_document(document)


def get_download_info(owner_id, document_id):
    document = get_document(document_id, owner_id)

    if document is None:
        raise FileNotFoundError("Document not found")

    path = Path(document["storage_path"])

    if not path.is_file():
        raise FileNotFoundError("Stored document file is missing")

    return path, document["original_filename"]


def edit_user_document(owner_id, document_id, updates):
    if not updates or not set(updates).issubset({"title", "category"}):
        raise ValueError("Provide a title or category to update")

    updates = dict(updates)

    if "title" in updates:
        title = updates["title"]

        if not isinstance(title, str) or not title.strip():
            raise ValueError("Title cannot be empty")

        updates["title"] = title.strip()

        if len(updates["title"]) > 255:
            raise ValueError("Title must not exceed 255 characters")

    if "category" in updates and updates["category"] is not None:
        category = updates["category"]

        if not isinstance(category, str) or len(category) > 100:
            raise ValueError("Category must not exceed 100 characters")

        updates["category"] = category.strip() or None

    document = update_document(document_id, owner_id, updates)

    if document is None:
        raise FileNotFoundError("Document not found")

    return _public_document(document)


def delete_user_document(owner_id, document_id):
    document = delete_document(document_id, owner_id)

    if document is None:
        raise FileNotFoundError("Document not found")

    Path(document["storage_path"]).unlink(missing_ok=True)


def queue_reprocessing(owner_id, document_id):
    """Check ownership and reset a Processed/Failed document for reprocessing."""
    document = get_document(document_id, owner_id)

    if document is None:
        raise FileNotFoundError("Document not found")

    if document["processing_status"] not in {"Processed", "Failed"}:
        raise ValueError(
            "Only Processed or Failed documents can be reprocessed"
        )

    updated = mark_document_uploaded(document_id, owner_id)
    return _public_document(updated)