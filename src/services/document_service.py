
import json
import logging
import os
import uuid
import zipfile

from io import BytesIO
from pathlib import Path

from src.repositories.admin_repository import list_categories

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
    save_analysis_results,
)

from src.services.text_extractor import (
    extract_text,
    TextExtractionError,
)

from src.services.content_analyzer import analyze_document_text

from src.services.embedding_service import (
    split_into_passages,
    encode_passages,
)

from src.services.vector_store_service import (
    index_document_passages,
    delete_document_index,
)


logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _safe_filename(filename):
    """Remove directory components from an uploaded filename."""
    return (
        (filename or "")
        .replace("\\", "/")
        .split("/")[-1]
        .strip()
    )


def _validate_file(filename, content):
    """Validate extension, file content and maximum file size."""
    filename = _safe_filename(filename)
    extension = Path(filename).suffix.lower()

    if not filename or extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Only PDF, DOCX and TXT files are supported"
        )

    if not content:
        raise ValueError("The uploaded file is empty")

    if len(content) > MAX_FILE_SIZE:
        raise ValueError("The file must not exceed 10 MB")

    if extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise ValueError(
                "The file content does not match PDF format"
            )

    elif extension == ".docx":
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                if "word/document.xml" not in archive.namelist():
                    raise ValueError("Invalid DOCX document")
        except (zipfile.BadZipFile, OSError) as exc:
            raise ValueError("Invalid DOCX file") from exc

    elif extension == ".txt":
        if b"\x00" in content:
            raise ValueError(
                "The TXT file contains binary data"
            )

        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "The TXT file must use UTF-8 encoding"
            ) from exc

    return filename, extension


def _public_document(document):
    """Return public metadata without exposing private fields."""
    if document is None:
        return None

    result = dict(document)

    try:
        result["keywords"] = json.loads(
            result.get("keywords_json") or "[]"
        )
    except (ValueError, TypeError):
        result["keywords"] = []

    try:
        result["topics"] = json.loads(
            result.get("topics_json") or "[]"
        )
    except (ValueError, TypeError):
        result["topics"] = []

    for field in (
        "storage_path",
        "owner_id",
        "extracted_text",
        "keywords_json",
        "topics_json",
    ):
        result.pop(field, None)

    return result


def upload_document(owner_id, filename, content, title=None):
    """Validate and store an uploaded document."""
    filename, extension = _validate_file(filename, content)

    selected_title = (title or "").strip() or filename

    if len(selected_title) > 255:
        raise ValueError(
            "Title must not exceed 255 characters"
        )

    storage_dir = Path(
        os.getenv("DOCUMENT_STORAGE_PATH", "storage")
    ).resolve()

    storage_dir.mkdir(parents=True, exist_ok=True)

    stored_path = storage_dir / (
        f"{uuid.uuid4().hex}{extension}"
    )

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

        return _public_document(document)

    except Exception:
        stored_path.unlink(missing_ok=True)
        raise


def _mark_processing_failed(document_id, owner_id, reason):
    """Remove stale vectors and record a readable failure reason."""
    try:
        delete_document_index(document_id, owner_id)
    except Exception:
        logger.exception(
            "Could not remove vector index for document %s",
            document_id,
        )

    try:
        mark_document_failed(
            document_id,
            owner_id,
            str(reason),
        )
    except Exception:
        logger.exception(
            "Could not update failure status for document %s",
            document_id,
        )


def process_document(document_id, owner_id):
    """
    Extract, analyse and index a stored document.

    Status transitions:
    Uploaded -> Processing -> Processed or Failed
    """
    document = get_document(document_id, owner_id)

    if document is None:
        logger.warning(
            "Document %s not found for processing",
            document_id,
        )
        return

    try:
        # 1. Update the processing status.
        mark_document_processing(
            document_id,
            owner_id,
        )

        # 2. Read the stored file.
        stored_path = Path(document["storage_path"])
        content = stored_path.read_bytes()

        # 3. Extract text from PDF, DOCX or TXT.
        extracted = extract_text(
            document["original_filename"],
            content,
        )

        # 4. Split extracted text into overlapping passages.
        passages = split_into_passages(extracted)

        if not passages:
            raise TextExtractionError(
                "No text passages could be generated "
                "from the document."
            )

        # 5. Generate semantic embeddings for the passages.
        embeddings = encode_passages(passages)

        if len(embeddings) != len(passages):
            raise RuntimeError(
                "Embedding count does not match passage count"
            )

        # 6. Analyse the document using its passage embeddings
        # and the categories maintained by the administrator.
        categories = list_categories()

        analysis = analyze_document_text(
            extracted,
            passage_embeddings=embeddings,
            categories=categories,
        )

        # 7. Index the passages for semantic search.
        # Existing vectors for this document are replaced.
        index_document_passages(
            document_id=document_id,
            owner_id=owner_id,
            file_type=document["file_type"],
            passages=passages,
            embeddings=embeddings,
        )

        # 8. Persist category, confidence, keywords and topics.
        save_analysis_results(
            document_id=document_id,
            owner_id=owner_id,
            category=analysis["category"],
            confidence=analysis["confidence"],
            keywords=analysis["keywords"],
            topics=analysis["topics"],
        )

        # 9. Mark the document Processed after indexing and analysis.
        mark_document_processed(
            document_id,
            owner_id,
            extracted,
        )

        logger.info(
            "Document %s processed successfully; %s passages indexed",
            document_id,
            len(passages),
        )

    except TextExtractionError as exc:
        logger.warning(
            "Text extraction failed for document %s: %s",
            document_id,
            exc,
        )

        _mark_processing_failed(
            document_id,
            owner_id,
            str(exc),
        )

    except OSError:
        logger.exception(
            "Stored file could not be read for document %s",
            document_id,
        )

        _mark_processing_failed(
            document_id,
            owner_id,
            "The stored file could not be read. "
            "Please upload it again.",
        )

    except Exception:
        logger.exception(
            "Unexpected processing failure for document %s",
            document_id,
        )

        _mark_processing_failed(
            document_id,
            owner_id,
            "Document processing failed unexpectedly. "
            "Please retry processing.",
        )


def list_user_documents(owner_id, offset=0, limit=20):
    """List documents belonging to the authenticated user."""
    documents, total = list_documents(
        owner_id,
        offset=offset,
        limit=limit,
    )

    return {
        "items": [
            _public_document(document)
            for document in documents
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def get_user_document(owner_id, document_id):
    """Get details for a document owned by the user."""
    document = get_document(
        document_id,
        owner_id,
    )

    if document is None:
        raise FileNotFoundError("Document not found")

    return _public_document(document)


def get_download_info(owner_id, document_id):
    """Return the original file path and filename."""
    document = get_document(
        document_id,
        owner_id,
    )

    if document is None:
        raise FileNotFoundError("Document not found")

    path = Path(document["storage_path"])

    if not path.is_file():
        raise FileNotFoundError(
            "Stored document file is missing"
        )

    return path, document["original_filename"]


def edit_user_document(owner_id, document_id, updates):
    """Update a document title or manually assigned category."""
    if not updates or not set(updates).issubset(
        {"title", "category"}
    ):
        raise ValueError(
            "Provide a title or category to update"
        )

    updates = dict(updates)

    if "title" in updates:
        title = updates["title"]

        if not isinstance(title, str) or not title.strip():
            raise ValueError("Title cannot be empty")

        updates["title"] = title.strip()

        if len(updates["title"]) > 255:
            raise ValueError(
                "Title must not exceed 255 characters"
            )

    if "category" in updates:
        category = updates["category"]

        if category is not None:
            if (
                not isinstance(category, str)
                or len(category) > 100
            ):
                raise ValueError(
                    "Category must not exceed 100 characters"
                )

            updates["category"] = category.strip() or None

    document = update_document(
        document_id,
        owner_id,
        updates,
    )

    if document is None:
        raise FileNotFoundError("Document not found")

    return _public_document(document)


def delete_user_document(owner_id, document_id):
    """Delete the document, its vector index and stored file."""
    document = get_document(
        document_id,
        owner_id,
    )

    if document is None:
        raise FileNotFoundError("Document not found")

    # Remove indexed passages before deleting the database record.
    delete_document_index(
        document_id,
        owner_id,
    )

    deleted = delete_document(
        document_id,
        owner_id,
    )

    if deleted is None:
        raise FileNotFoundError("Document not found")

    Path(document["storage_path"]).unlink(
        missing_ok=True
    )


def queue_reprocessing(owner_id, document_id):
    """Reset a Processed or Failed document for reprocessing."""
    document = get_document(
        document_id,
        owner_id,
    )

    if document is None:
        raise FileNotFoundError("Document not found")

    if document["processing_status"] not in {
        "Processed",
        "Failed",
    }:
        raise ValueError(
            "Only Processed or Failed documents "
            "can be reprocessed"
        )

    # Remove old vectors so reprocessing cannot leave duplicates.
    delete_document_index(
        document_id,
        owner_id,
    )

    updated = mark_document_uploaded(
        document_id,
        owner_id,
    )

    return _public_document(updated)
