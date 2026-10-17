"""
Vector store abstraction over Qdrant.
Handles chunk storage, semantic retrieval, and per-video records
(metadata, cached summary and notes) so nothing depends on local disk.

Uses Qdrant Cloud when QDRANT_URL is set, otherwise an embedded local Qdrant.
"""

import logging
import uuid
from typing import Any, Optional
from qdrant_client import QdrantClient, models

from backend.config import get_settings
from backend.services import embedding_service

logger = logging.getLogger(__name__)

CHUNKS_COLLECTION = "vidmind_chunks"
VIDEOS_COLLECTION = "vidmind_videos"

# Module-level Qdrant client cache
_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    """Get or create the Qdrant client and make sure collections exist."""
    global _client
    if _client is None:
        settings = get_settings()
        if settings.QDRANT_URL:
            logger.info(f"Connecting to Qdrant Cloud at: {settings.QDRANT_URL}")
            client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
        else:
            logger.info(f"Using local embedded Qdrant at: {settings.QDRANT_PATH}")
            client = QdrantClient(path=settings.QDRANT_PATH)
        _ensure_collections(client, is_server=bool(settings.QDRANT_URL))
        _client = client
    return _client


def close_client() -> None:
    """Close the Qdrant client (releases the local storage lock)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


def _ensure_collections(client: QdrantClient, is_server: bool) -> None:
    """Create the chunk and video collections on first run."""
    if not client.collection_exists(CHUNKS_COLLECTION):
        client.create_collection(
            collection_name=CHUNKS_COLLECTION,
            vectors_config=models.VectorParams(
                size=embedding_service.get_embedding_dim(),
                distance=models.Distance.COSINE,
            ),
        )
        # Qdrant Cloud needs a payload index to filter by video_id (local mode ignores it)
        if is_server:
            client.create_payload_index(
                collection_name=CHUNKS_COLLECTION,
                field_name="video_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
        logger.info(f"Created collection '{CHUNKS_COLLECTION}'")

    if not client.collection_exists(VIDEOS_COLLECTION):
        # Records only — a 1-dim placeholder vector keeps this portable across Qdrant versions
        client.create_collection(
            collection_name=VIDEOS_COLLECTION,
            vectors_config=models.VectorParams(size=1, distance=models.Distance.DOT),
        )
        logger.info(f"Created collection '{VIDEOS_COLLECTION}'")


def _video_filter(video_id: str) -> models.Filter:
    return models.Filter(
        must=[models.FieldCondition(key="video_id", match=models.MatchValue(value=video_id))]
    )


def _point_id(*parts: Any) -> str:
    """Deterministic UUID so re-processing a video overwrites instead of duplicating."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "/".join(str(p) for p in parts)))


# =============================================================================
# Chunks
# =============================================================================

def video_exists(video_id: str) -> bool:
    """Check if a video has already been processed and stored."""
    return get_chunk_count(video_id) > 0


def store_chunks(video_id: str, chunks: list[dict]) -> int:
    """
    Embed and store transcript chunks.

    Args:
        video_id: YouTube video ID
        chunks: List of chunk dicts with 'text', 'chunk_index' and 'metadata' keys

    Returns:
        Number of chunks stored
    """
    if not chunks:
        logger.warning("No chunks to store")
        return 0

    client = get_client()
    vectors = embedding_service.generate_embeddings([chunk["text"] for chunk in chunks])

    points = [
        models.PointStruct(
            id=_point_id(video_id, chunk["chunk_index"]),
            vector=vector,
            payload={**chunk["metadata"], "text": chunk["text"]},
        )
        for chunk, vector in zip(chunks, vectors)
    ]

    # Upsert in batches to keep request sizes small
    batch_size = 100
    for i in range(0, len(points), batch_size):
        client.upsert(collection_name=CHUNKS_COLLECTION, points=points[i : i + batch_size])

    logger.info(f"Stored {len(points)} chunks for video {video_id}")
    return len(points)


def _payload_to_chunk(payload: dict) -> dict:
    payload = dict(payload or {})
    text = payload.pop("text", "")
    return {"text": text, "metadata": payload}


def query_chunks(
    video_id: str,
    query_text: str,
    top_k: Optional[int] = None,
) -> list[dict]:
    """
    Semantic similarity search over one video's chunks.

    Returns:
        List of dicts with 'text', 'metadata', and 'distance' keys,
        ordered by relevance (most relevant first).
    """
    settings = get_settings()
    top_k = top_k or settings.TOP_K

    try:
        result = get_client().query_points(
            collection_name=CHUNKS_COLLECTION,
            query=embedding_service.generate_query_embedding(query_text),
            query_filter=_video_filter(video_id),
            limit=top_k,
            with_payload=True,
        )
        formatted = [
            {**_payload_to_chunk(point.payload), "distance": 1.0 - point.score}
            for point in result.points
        ]
        logger.info(f"Query returned {len(formatted)} results for '{query_text[:50]}...'")
        return formatted

    except Exception as e:
        logger.error(f"Qdrant query failed: {e}")
        return []


def get_all_chunks(video_id: str) -> list[dict]:
    """
    Retrieve all stored chunks for a video (used for summary/note generation).

    Returns:
        List of dicts with 'text' and 'metadata', ordered by chunk_index.
    """
    try:
        client = get_client()
        chunks = []
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=CHUNKS_COLLECTION,
                scroll_filter=_video_filter(video_id),
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            chunks.extend(_payload_to_chunk(p.payload) for p in points)
            if offset is None:
                break

        chunks.sort(key=lambda c: c["metadata"].get("chunk_index", 0))
        return chunks

    except Exception as e:
        logger.error(f"Failed to get all chunks: {e}")
        return []


def get_chunk_count(video_id: str) -> int:
    """Get the number of stored chunks for a video."""
    try:
        return get_client().count(
            collection_name=CHUNKS_COLLECTION,
            count_filter=_video_filter(video_id),
            exact=True,
        ).count
    except Exception as e:
        logger.warning(f"Error counting chunks for {video_id}: {e}")
        return 0


# =============================================================================
# Video records (metadata, cached summary and notes)
# =============================================================================

def get_video_record(video_id: str) -> dict:
    """Return the stored record for a video, or {} if none."""
    try:
        points = get_client().retrieve(
            collection_name=VIDEOS_COLLECTION,
            ids=[_point_id("video", video_id)],
            with_payload=True,
        )
        return dict(points[0].payload or {}) if points else {}
    except Exception as e:
        logger.warning(f"Failed to load record for {video_id}: {e}")
        return {}


def update_video_record(video_id: str, **fields: Any) -> None:
    """Merge fields into a video's record, creating it if needed."""
    try:
        record = get_video_record(video_id)
        record.update(fields, video_id=video_id)
        get_client().upsert(
            collection_name=VIDEOS_COLLECTION,
            points=[models.PointStruct(id=_point_id("video", video_id), vector=[1.0], payload=record)],
        )
    except Exception as e:
        logger.warning(f"Failed to save record for {video_id}: {e}")
