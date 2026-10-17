"""
Embedding service using FastEmbed (ONNX Runtime).
Runs locally on CPU with a small memory footprint — no PyTorch, no external API.
"""

import logging
from typing import Optional
from fastembed import TextEmbedding

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Module-level model cache to avoid reloading
_model: Optional[TextEmbedding] = None


def get_embedding_model() -> TextEmbedding:
    """
    Lazy-load and cache the FastEmbed model.
    First call downloads the model (~90MB for all-MiniLM-L6-v2) into EMBEDDING_CACHE_DIR.
    """
    global _model
    if _model is None:
        settings = get_settings()
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        _model = TextEmbedding(
            model_name=settings.EMBEDDING_MODEL,
            cache_dir=settings.EMBEDDING_CACHE_DIR,
        )
        logger.info(f"Embedding model loaded: {settings.EMBEDDING_MODEL}")
    return _model


def get_embedding_dim() -> int:
    """Return the vector size of the configured embedding model."""
    return len(generate_query_embedding("dimension probe"))


def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a list of texts.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors (each is a list of floats)
    """
    if not texts:
        return []

    model = get_embedding_model()
    embeddings = [vec.tolist() for vec in model.embed(texts, batch_size=32)]

    logger.info(f"Generated {len(embeddings)} embeddings (dim={len(embeddings[0])})")
    return embeddings


def generate_query_embedding(query: str) -> list[float]:
    """Generate a single embedding for a search query."""
    model = get_embedding_model()
    return next(iter(model.query_embed(query))).tolist()
