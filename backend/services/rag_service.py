"""
RAG (Retrieval-Augmented Generation) service.
Orchestrates: Question → Embed → Retrieve → Context → LLM → Grounded Answer.
"""

import logging
from backend.config import get_settings
from backend.services import vector_store, llm_service
from backend.utils.helpers import seconds_to_timestamp, timestamp_to_youtube_url
from backend.models.schemas import SourceTimestamp

logger = logging.getLogger(__name__)

# =============================================================================
# System Prompts
# =============================================================================

QA_SYSTEM_PROMPT = """You are a helpful AI assistant that answers questions about a YouTube video.

STRICT RULES:
1. Answer the user's question using ONLY the provided transcript context below.
2. Do NOT use any outside knowledge or information not present in the context.
3. If the answer cannot be determined from the provided context, say:
   "I couldn't find that information in the video transcript."
4. Do NOT fabricate facts, examples, formulas, or definitions.
5. When possible, mention the relevant timestamp using the format ⏱ MM:SS.
6. Be concise but thorough.
7. Use markdown formatting for readability.

TRANSCRIPT CONTEXT:
{context}
"""


def build_context(retrieved_chunks: list[dict]) -> str:
    """
    Build a context string from retrieved chunks with timestamp headers.

    Example output:
        [⏱ 12:35 - 13:20]
        Vector databases store numerical representations...

        [⏱ 18:42 - 19:15]
        Semantic search enables finding similar content...
    """
    context_parts = []
    for chunk in retrieved_chunks:
        metadata = chunk.get("metadata", {})
        start = metadata.get("start_time", 0)
        end = metadata.get("end_time", 0)
        start_ts = seconds_to_timestamp(start)
        end_ts = seconds_to_timestamp(end)

        context_parts.append(
            f"[⏱ {start_ts} - {end_ts}]\n{chunk['text']}"
        )

    return "\n\n".join(context_parts)


def extract_sources(retrieved_chunks: list[dict], video_id: str) -> list[SourceTimestamp]:
    """Extract source timestamps from retrieved chunks."""
    sources = []
    seen_starts = set()

    for chunk in retrieved_chunks:
        metadata = chunk.get("metadata", {})
        start_time = metadata.get("start_time", 0)

        # Deduplicate by start time (rounded to seconds)
        start_key = int(start_time)
        if start_key in seen_starts:
            continue
        seen_starts.add(start_key)

        sources.append(SourceTimestamp(
            start_time=start_time,
            end_time=metadata.get("end_time", 0),
            text_preview=chunk["text"][:120] + "..." if len(chunk["text"]) > 120 else chunk["text"],
            timestamp_display=seconds_to_timestamp(start_time),
            youtube_url=timestamp_to_youtube_url(video_id, start_time),
        ))

    # Sort by time
    sources.sort(key=lambda s: s.start_time)
    return sources


def ask_question(
    video_id: str,
    question: str,
    conversation_history: list[dict] | None = None,
    top_k: int | None = None,
) -> dict:
    """
    Full RAG pipeline: Question → Retrieve → Context → LLM → Answer + Sources.

    Args:
        video_id: YouTube video ID
        question: User's question
        conversation_history: Previous Q&A turns for follow-up context
        top_k: Number of chunks to retrieve

    Returns:
        Dict with 'answer', 'sources', 'question' keys
    """
    settings = get_settings()
    top_k = top_k or settings.TOP_K

    # Step 1: Retrieve relevant chunks from ChromaDB
    logger.info(f"RAG query: '{question}' for video {video_id}")
    retrieved = vector_store.query_chunks(video_id, question, top_k=top_k)

    if not retrieved:
        return {
            "question": question,
            "answer": "I couldn't find relevant information in the video transcript to answer this question.",
            "sources": [],
        }

    # Step 2: Build context from retrieved chunks
    context = build_context(retrieved)

    # Step 3: Build the prompt with context
    system_prompt = QA_SYSTEM_PROMPT.format(context=context)

    # Step 4: Generate answer (with conversation history for follow-ups)
    if conversation_history:
        # Trim conversation history to prevent context overflow
        max_history = settings.MAX_CONVERSATION_HISTORY
        trimmed_history = conversation_history[-max_history:]
        answer = llm_service.generate_response_with_history(
            system_prompt=system_prompt,
            conversation_history=trimmed_history,
            user_prompt=question,
        )
    else:
        answer = llm_service.generate_response(
            system_prompt=system_prompt,
            user_prompt=question,
        )

    # Step 5: Extract source timestamps
    sources = extract_sources(retrieved, video_id)

    logger.info(f"RAG answer generated with {len(sources)} sources")
    return {
        "question": question,
        "answer": answer,
        "sources": sources,
    }
