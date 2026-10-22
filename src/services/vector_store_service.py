import os
from pathlib import Path

import chromadb


VECTOR_PATH = Path(
    os.getenv("VECTOR_STORE_PATH", "vector_store")
).resolve()

_client = chromadb.PersistentClient(path=str(VECTOR_PATH))

_collection = _client.get_or_create_collection(
    name="document_passages",
    metadata={"hnsw:space": "cosine"},
)


def delete_document_index(document_id, owner_id):
    """Remove old passage vectors for one owned document."""
    _collection.delete(
        where={
            "$and": [
                {"owner_id": str(owner_id)},
                {"document_id": str(document_id)},
            ]
        }
    )


def index_document_passages(
    document_id,
    owner_id,
    file_type,
    passages,
    embeddings,
):
    """Replace a document's existing vectors with its latest passages."""
    if len(passages) != len(embeddings):
        raise ValueError("Passages and embeddings must have equal lengths")

    delete_document_index(document_id, owner_id)

    if not passages:
        return

    ids = [
        f"user-{owner_id}-document-{document_id}-passage-{i}"
        for i in range(len(passages))
    ]

    metadatas = [
        {
            "owner_id": str(owner_id),
            "document_id": str(document_id),
            "passage_index": i,
            "file_type": file_type.lower(),
        }
        for i in range(len(passages))
    ]

    _collection.add(
        ids=ids,
        documents=passages,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def search_passages(owner_id, query_embedding, limit=1000):
    """Return nearest passages belonging to one user only."""
    owned = _collection.get(
        where={"owner_id": str(owner_id)},
        include=["metadatas"],
    )

    count = len(owned["ids"])

    if count == 0:
        return []

    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=min(count, limit),
        where={"owner_id": str(owner_id)},
        include=["documents", "metadatas", "distances"],
    )

    rows = []

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for vector_id, passage, metadata, distance in zip(
        ids, documents, metadatas, distances
    ):
        rows.append({
            "vector_id": vector_id,
            "passage": passage,
            "metadata": metadata,
            "distance": float(distance),
        })

    return rows