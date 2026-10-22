import os
from functools import lru_cache

from sentence_transformers import SentenceTransformer


@lru_cache(maxsize=1)
def _get_model():
    model_name = os.getenv(
        "EMBEDDING_MODEL",
        "sentence-transformers/all-MiniLM-L6-v2",
    )

    return SentenceTransformer(model_name, device="cpu")


def split_into_passages(
    text,
    max_words=150,
    overlap=30,
    max_passages=100,
):
    """Split text into overlapping passages, with a 100-passage cap."""
    if max_words < 1:
        raise ValueError("max_words must be positive")

    if overlap < 0 or overlap >= max_words:
        raise ValueError("overlap must be between 0 and max_words - 1")

    if max_passages < 1:
        raise ValueError("max_passages must be positive")

    words = (text or "").split()

    if not words:
        return []

    step = max_words - overlap
    passages = []

    for start in range(0, len(words), step):
        # Avoid a redundant tail containing only overlap words.
        if start > 0 and len(words) - start <= overlap:
            break

        passages.append(" ".join(words[start:start + max_words]))

        if start + max_words >= len(words):
            break

        if len(passages) >= max_passages:
            break

    return passages


def encode_passages(texts):
    """Generate normalized embeddings in batches."""
    if not texts:
        return []

    vectors = _get_model().encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    return vectors.tolist()