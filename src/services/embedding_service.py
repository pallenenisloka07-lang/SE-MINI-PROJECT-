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


def split_into_passages(text, max_words=150):
    """Split extracted text into passages of about 150 words."""
    words = text.split()

    if not words:
        return []

    return [
        " ".join(words[i:i + max_words])
        for i in range(0, len(words), max_words)
    ]


def encode_passages(texts):
    """Generate normalized semantic embeddings."""
    if not texts:
        return []

    vectors = _get_model().encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

    return vectors.tolist()