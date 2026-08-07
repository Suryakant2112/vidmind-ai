"""
Embedding service using Sentence Transformers.
Runs locally on CPU — no external API needed.
"""

import logging
from typing import Optional
from sentence_transformers import SentenceTransformer

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Module-level model cache to avoid reloading
_model: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    """
    Lazy-load and cache the Sentence Transformer model.
    First call downloads the model (~22MB for all-MiniLM-L6-v2).
    Subsequent calls return the cached instance.
    """
    global _model
    if _model is None:
        settings = get_settings()
        model_name = settings.EMBEDDING_MODEL
        logger.info(f"Loading embedding model: {model_name}")
        _model = SentenceTransformer(model_name, device="cpu")
        logger.info(f"Embedding model loaded: {model_name}")
    return _model


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts using Sentence Transformers.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors (each is a list of floats)
    """
    if not texts:
        return []

    model = get_embedding_model()
    embeddings = model.encode(
        texts,
        show_progress_bar=False,
        batch_size=32,
        normalize_embeddings=True,
    )

    logger.info(f"Generated {len(embeddings)} embeddings (dim={len(embeddings[0])})")
    return embeddings.tolist()


def generate_query_embedding(query: str) -> list[float]:
    """Generate a single embedding for a search query."""
    model = get_embedding_model()
    embedding = model.encode(
        query,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return embedding.tolist()
