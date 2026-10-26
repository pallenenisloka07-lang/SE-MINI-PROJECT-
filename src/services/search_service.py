import os
import re

from src.repositories.document_repository import (
    list_documents,
    get_document,
)
from src.services.embedding_service import encode_passages
from src.services.vector_store_service import search_passages


def _owner_documents(owner_id):
    summaries, _ = list_documents(
        owner_id,
        offset=0,
        limit=1000,
    )

    documents = []

    for summary in summaries:
        document = get_document(summary["id"], owner_id)

        if (
            document
            and document.get("processing_status") == "Processed"
        ):
            documents.append(document)

    return documents


def _matches_filters(
    document,
    category=None,
    file_type=None,
    date_from=None,
    date_to=None,
):
    if category and (
        (document.get("category") or "").casefold()
        != category.casefold()
    ):
        return False

    if file_type and (
        (document.get("file_type") or "").casefold()
        != file_type.casefold().lstrip(".")
    ):
        return False

    uploaded = document.get("created_at")

    if uploaded and date_from and uploaded.date() < date_from:
        return False

    if uploaded and date_to and uploaded.date() > date_to:
        return False

    return True


def _snippet(text, terms=(), width=220):
    text = (text or "").strip()

    if not text:
        return ""

    lower = text.casefold()
    positions = [
        lower.find(term.casefold())
        for term in terms
        if term and lower.find(term.casefold()) >= 0
    ]

    start = max(0, min(positions) - 70) if positions else 0
    excerpt = text[start:start + width]

    if start:
        excerpt = "…" + excerpt

    if start + width < len(text):
        excerpt += "…"

    return excerpt


def _public_result(document, snippet, relevance=None):
    result = {
        "id": document["id"],
        "title": document["title"],
        "category": document.get("category"),
        "file_type": document["file_type"],
        "uploaded_at": (
            document["created_at"].isoformat()
            if document.get("created_at")
            else None
        ),
        "snippet": snippet,
    }

    if relevance is not None:
        result["relevance_score"] = round(relevance, 2)

    return result


def _paginate(items, page, page_size=10):
    start = (page - 1) * page_size

    return {
        "items": items[start:start + page_size],
        "total": len(items),
        "page": page,
        "page_size": page_size,
        "total_pages": (
            (len(items) + page_size - 1) // page_size
        ),
    }


def keyword_search(
    owner_id,
    query,
    page=1,
    category=None,
    file_type=None,
    date_from=None,
    date_to=None,
):
    """Search title and extracted text; all query terms must match."""
    terms = re.findall(r"[a-zA-Z0-9]+", query.casefold())

    if not terms:
        return _paginate([], page)

    matches = []

    for document in _owner_documents(owner_id):
        if not _matches_filters(
            document, category, file_type, date_from, date_to
        ):
            continue

        title = document.get("title") or ""
        text = document.get("extracted_text") or ""
        combined = f"{title} {text}".casefold()

        if not all(term in combined for term in terms):
            continue

        score = sum(
            title.casefold().count(term) * 3
            + text.casefold().count(term)
            for term in terms
        )

        matches.append({
            "_score": score,
            "result": _public_result(
                document,
                _snippet(text or title, terms),
            ),
            "created_at": document.get("created_at"),
        })

    matches.sort(
        key=lambda item: (
            item["_score"],
            item["created_at"] or "",
        ),
        reverse=True,
    )

    return _paginate(
        [item["result"] for item in matches],
        page,
    )


def semantic_search(
    owner_id,
    query,
    page=1,
    category=None,
    file_type=None,
    date_from=None,
    date_to=None,
):
    """Find relevant passages using pretrained sentence embeddings."""
    query_embedding = encode_passages([query])[0]

    passages = search_passages(
        owner_id,
        query_embedding,
        limit=1000,
    )

    best_by_document = {}

    for match in passages:
        metadata = match["metadata"]
        document_id = int(metadata["document_id"])
        service_document_id = int(
            metadata.get("service_document_id", document_id)
        )

        # Chroma cosine distance = 1 - cosine similarity.
        similarity = 1.0 - match["distance"]
        relevance = max(0.0, min(1.0, similarity)) * 100.0

        minimum = float(
            os.getenv("MIN_SEARCH_RELEVANCE", "20")
        )

        if relevance < minimum:
            continue

        document = get_document(service_document_id, owner_id)

        if not document:
            continue

        if document.get("processing_status") != "Processed":
            continue

        if not _matches_filters(
            document, category, file_type, date_from, date_to
        ):
            continue

        previous = best_by_document.get(document_id)

        if previous is None or relevance > previous["relevance"]:
            best_by_document[document_id] = {
                "relevance": relevance,
                "document": document,
                "passage": match["passage"],
                "public_document_id": document_id,
            }

    ranked = sorted(
        best_by_document.values(),
        key=lambda item: item["relevance"],
        reverse=True,
    )

    results = []
    for item in ranked:
        result = _public_result(
            item["document"],
            _snippet(item["passage"]),
            item["relevance"],
        )
        result["id"] = item["public_document_id"]
        results.append(result)

    return _paginate(results, page)