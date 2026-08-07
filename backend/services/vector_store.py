"""
Vector store abstraction over ChromaDB.
Handles persistent storage, embedding storage, and semantic retrieval.
"""

import logging
from typing import Optional
import chromadb
from chromadb.utils import embedding_functions

from backend.config import get_settings

logger = logging.getLogger(__name__)

# Module-level ChromaDB client cache
_chroma_client: Optional[chromadb.PersistentClient] = None


def get_chroma_client() -> chromadb.PersistentClient:
    """Get or create the persistent ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        settings = get_settings()
        path = settings.CHROMA_DB_PATH
        logger.info(f"Initializing ChromaDB PersistentClient at: {path}")
        _chroma_client = chromadb.PersistentClient(path=path)
    return _chroma_client


def get_embedding_function():
    """Get the ChromaDB-compatible Sentence Transformer embedding function."""
    settings = get_settings()
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=settings.EMBEDDING_MODEL,
        device="cpu",
    )


def get_collection_name(video_id: str) -> str:
    """Generate a collection name from a video ID."""
    # ChromaDB collection names: 3-63 chars, alphanumeric + underscores/hyphens
    return f"yt_{video_id}"


def video_exists(video_id: str) -> bool:
    """
    Check if a video has already been processed and stored in ChromaDB.

    Returns True if the collection exists and has documents.
    """
    try:
        client = get_chroma_client()
        collection_name = get_collection_name(video_id)
        existing = client.list_collections()
        
        # Check if our collection name exists
        for col in existing:
            col_name = col if isinstance(col, str) else getattr(col, 'name', str(col))
            if col_name == collection_name:
                collection = client.get_collection(
                    name=collection_name,
                    embedding_function=get_embedding_function(),
                )
                count = collection.count()
                logger.info(f"Collection '{collection_name}' exists with {count} documents")
                return count > 0
        return False
    except Exception as e:
        logger.warning(f"Error checking video existence: {e}")
        return False


def store_chunks(video_id: str, chunks: list[dict]) -> int:
    """
    Store transcript chunks with embeddings in ChromaDB.

    Args:
        video_id: YouTube video ID
        chunks: List of chunk dicts with 'text' and 'metadata' keys

    Returns:
        Number of documents stored
    """
    if not chunks:
        logger.warning("No chunks to store")
        return 0

    client = get_chroma_client()
    collection_name = get_collection_name(video_id)

    # Get or create the collection with our embedding function
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=get_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )

    # Prepare data for ChromaDB
    ids = [f"{video_id}_chunk_{chunk['chunk_index']}" for chunk in chunks]
    documents = [chunk["text"] for chunk in chunks]
    metadatas = [chunk["metadata"] for chunk in chunks]

    # Upsert in batches (ChromaDB handles batching internally but
    # we limit to avoid memory issues with very large transcripts)
    batch_size = 100
    total_stored = 0

    for i in range(0, len(documents), batch_size):
        batch_ids = ids[i : i + batch_size]
        batch_docs = documents[i : i + batch_size]
        batch_meta = metadatas[i : i + batch_size]

        collection.upsert(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_meta,
        )
        total_stored += len(batch_ids)

    logger.info(f"Stored {total_stored} chunks in collection '{collection_name}'")
    return total_stored


def query_chunks(
    video_id: str,
    query_text: str,
    top_k: Optional[int] = None,
) -> list[dict]:
    """
    Perform semantic similarity search against stored video chunks.

    Args:
        video_id: YouTube video ID
        query_text: The search query
        top_k: Number of results to return (default from config)

    Returns:
        List of dicts with 'text', 'metadata', and 'distance' keys,
        ordered by relevance (most relevant first).
    """
    settings = get_settings()
    top_k = top_k or settings.TOP_K

    try:
        client = get_chroma_client()
        collection_name = get_collection_name(video_id)

        collection = client.get_collection(
            name=collection_name,
            embedding_function=get_embedding_function(),
        )

        results = collection.query(
            query_texts=[query_text],
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        # Format results
        formatted = []
        if results and results["documents"] and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                formatted.append({
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0.0,
                })

        logger.info(
            f"Query returned {len(formatted)} results for '{query_text[:50]}...'"
        )
        return formatted

    except Exception as e:
        logger.error(f"ChromaDB query failed: {e}")
        return []


def get_all_chunks(video_id: str) -> list[dict]:
    """
    Retrieve all stored chunks for a video (used for summary/note generation).

    Returns:
        List of dicts with 'text' and 'metadata', ordered by chunk_index.
    """
    try:
        client = get_chroma_client()
        collection_name = get_collection_name(video_id)

        collection = client.get_collection(
            name=collection_name,
            embedding_function=get_embedding_function(),
        )

        results = collection.get(
            include=["documents", "metadatas"],
        )

        chunks = []
        if results and results["documents"]:
            for i in range(len(results["documents"])):
                chunks.append({
                    "text": results["documents"][i],
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                })

        # Sort by chunk_index for ordered processing
        chunks.sort(
            key=lambda c: c.get("metadata", {}).get("chunk_index", 0)
        )

        return chunks

    except Exception as e:
        logger.error(f"Failed to get all chunks: {e}")
        return []


def get_chunk_count(video_id: str) -> int:
    """Get the number of stored chunks for a video."""
    try:
        client = get_chroma_client()
        collection_name = get_collection_name(video_id)
        collection = client.get_collection(
            name=collection_name,
            embedding_function=get_embedding_function(),
        )
        return collection.count()
    except Exception:
        return 0
