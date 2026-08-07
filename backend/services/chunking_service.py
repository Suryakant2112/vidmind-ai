"""
Semantic chunking service.
Splits transcript into meaningful, overlapping chunks with timestamp metadata.
"""

import logging
from typing import Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.config import get_settings
from backend.utils.helpers import seconds_to_timestamp, timestamp_to_youtube_url

logger = logging.getLogger(__name__)


def create_timestamped_documents(
    segments: list[dict],
    video_id: str,
    video_url: str,
) -> list[dict]:
    """
    Merge transcript segments into coherent text blocks, preserving timestamps.

    Each segment has {"text", "start", "duration"}.
    We merge adjacent segments into larger blocks before chunking,
    so that the text splitter works with coherent paragraphs.

    Returns a list of dicts:
        {"text": str, "start_time": float, "end_time": float}
    """
    if not segments:
        return []

    # Group segments into ~paragraph-sized blocks (5-8 segments each)
    # This creates more coherent input for the text splitter
    blocks = []
    current_texts = []
    current_start = segments[0]["start"]
    current_end = current_start

    for i, seg in enumerate(segments):
        current_texts.append(seg["text"])
        current_end = seg["start"] + seg.get("duration", 0)

        # Create a new block every ~5 segments or at natural breaks
        if len(current_texts) >= 5 or i == len(segments) - 1:
            block_text = " ".join(current_texts)
            blocks.append({
                "text": block_text,
                "start_time": current_start,
                "end_time": current_end,
            })
            current_texts = []
            if i + 1 < len(segments):
                current_start = segments[i + 1]["start"]

    return blocks


def chunk_transcript(
    segments: list[dict],
    video_id: str,
    video_url: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> list[dict]:
    """
    Split transcript into semantic chunks with metadata.

    Pipeline:
        1. Merge segments into paragraph blocks (preserving timestamps)
        2. Use RecursiveCharacterTextSplitter for intelligent splitting
        3. Attach metadata (video_id, timestamps, source) to each chunk

    Args:
        segments: List of transcript segments with {text, start, duration}
        video_id: YouTube video ID
        video_url: Full YouTube URL
        chunk_size: Characters per chunk (default from config)
        chunk_overlap: Overlap between chunks (default from config)

    Returns:
        List of chunk dicts with text, metadata, and timestamp info
    """
    settings = get_settings()
    chunk_size = chunk_size or settings.CHUNK_SIZE
    chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

    if not segments:
        logger.warning("No segments to chunk")
        return []

    # Step 1: Create timestamped document blocks
    blocks = create_timestamped_documents(segments, video_id, video_url)

    if not blocks:
        return []

    # Step 2: Use LangChain text splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", "? ", "! ", ", ", " ", ""],
    )

    # Step 3: Split each block and preserve timestamp metadata
    chunks = []
    chunk_index = 0

    for block in blocks:
        splits = text_splitter.split_text(block["text"])

        for split_text in splits:
            if not split_text.strip():
                continue

            # Calculate approximate timestamp for each sub-chunk
            # within the block based on character position
            block_text = block["text"]
            char_position = block_text.find(split_text[:50])  # Find start
            if char_position < 0:
                char_position = 0

            # Interpolate timestamp within the block
            time_range = block["end_time"] - block["start_time"]
            text_fraction = char_position / max(len(block_text), 1)
            estimated_start = block["start_time"] + (time_range * text_fraction)

            # End time: estimate based on chunk proportion
            chunk_fraction = len(split_text) / max(len(block_text), 1)
            estimated_end = estimated_start + (time_range * chunk_fraction)

            chunk = {
                "text": split_text,
                "chunk_index": chunk_index,
                "metadata": {
                    "video_id": video_id,
                    "video_url": video_url,
                    "start_time": round(estimated_start, 1),
                    "end_time": round(min(estimated_end, block["end_time"]), 1),
                    "chunk_index": chunk_index,
                    "source": "youtube",
                    "timestamp_display": seconds_to_timestamp(estimated_start),
                    "youtube_timestamp_url": timestamp_to_youtube_url(
                        video_id, estimated_start
                    ),
                },
            }
            chunks.append(chunk)
            chunk_index += 1

    logger.info(
        f"Chunked transcript into {len(chunks)} chunks "
        f"(chunk_size={chunk_size}, overlap={chunk_overlap})"
    )
    return chunks
