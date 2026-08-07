"""
AI summary generation service.
Uses hierarchical summarization for long transcripts to avoid context-window overflow.
"""

import json
import os
import logging
from typing import Optional

from backend.config import get_settings
from backend.services import vector_store, llm_service
from backend.utils.helpers import seconds_to_timestamp, timestamp_to_youtube_url, estimate_tokens

logger = logging.getLogger(__name__)

# =============================================================================
# Prompts
# =============================================================================

SECTION_SUMMARY_PROMPT = """You are an expert summarizer. Summarize the following section of a YouTube video transcript.

RULES:
- Summarize ONLY the content provided. Do NOT add outside information.
- Identify the main topics and key points discussed.
- Preserve important technical terms, definitions, and examples.
- Note the approximate timestamps using the format ⏱ MM:SS.
- Use clear, concise language.
- Use markdown formatting.

TRANSCRIPT SECTION:
{section_text}
"""

FINAL_SUMMARY_PROMPT = """You are an expert summarizer creating a comprehensive video summary.

Below are summaries of individual sections of a YouTube video. Combine them into a single, well-structured summary.

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

## Overview
A concise 2-3 sentence explanation of what the entire video covers.

## Main Topics
- Topic 1
- Topic 2
- Topic 3
(List all major topics discussed)

## Key Points
- Important concept or argument 1
- Important concept or argument 2
(List the most important ideas)

## Detailed Summary

### [Topic/Section Name]
Summary of this section...

### [Next Topic/Section Name]
Summary of this section...

(Organize by the major sections/topics of the video)

## Key Takeaways
1. Most important lesson 1
2. Most important lesson 2
3. Most important lesson 3

## Important Timestamps
- ⏱ MM:SS — Description of what happens at this point
- ⏱ MM:SS — Description of what happens at this point

RULES:
- Use ONLY the information from the section summaries below.
- Do NOT invent or fabricate information.
- Preserve technical terminology and definitions.
- Keep it educational and well-organized.

SECTION SUMMARIES:
{section_summaries}
"""

SHORT_VIDEO_SUMMARY_PROMPT = """You are an expert summarizer. Create a comprehensive summary of this YouTube video transcript.

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

## Overview
A concise 2-3 sentence explanation of what the entire video covers.

## Main Topics
- Topic 1
- Topic 2
(List all major topics discussed)

## Key Points
- Important concept or argument 1
- Important concept or argument 2

## Detailed Summary

### [Topic/Section Name]
Summary of this section...

### [Next Topic/Section Name]
Summary of this section...

## Key Takeaways
1. Most important lesson 1
2. Most important lesson 2

## Important Timestamps
- ⏱ MM:SS — Description of what happens at this point

RULES:
- Summarize ONLY the transcript content. Do NOT add outside information.
- Preserve important technical terms, definitions, and examples.
- Include relevant timestamps using the format ⏱ MM:SS.
- Use clear, well-organized markdown formatting.

TRANSCRIPT:
{transcript}
"""


# =============================================================================
# Caching
# =============================================================================

def _get_cache_path(video_id: str) -> str:
    """Get the cache file path for a video's summary."""
    settings = get_settings()
    cache_dir = os.path.join(settings.CACHE_DIR, video_id)
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "summary.json")


def _load_cached_summary(video_id: str) -> Optional[str]:
    """Load a cached summary if available."""
    path = _get_cache_path(video_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("summary")
        except Exception:
            pass
    return None


def _save_summary_cache(video_id: str, summary: str) -> None:
    """Save a generated summary to cache."""
    path = _get_cache_path(video_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"video_id": video_id, "summary": summary}, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to cache summary: {e}")


# =============================================================================
# Summary Generation
# =============================================================================

def generate_summary(video_id: str, force_regenerate: bool = False) -> dict:
    """
    Generate an AI summary for a processed video.

    Uses hierarchical summarization for long transcripts:
        1. Split into sections
        2. Summarize each section
        3. Combine into final structured summary

    Short transcripts (<3000 tokens) are summarized in a single pass.

    Args:
        video_id: YouTube video ID
        force_regenerate: If True, ignore cache

    Returns:
        Dict with 'summary' (markdown string) and 'cached' (bool)
    """
    # Check cache first
    if not force_regenerate:
        cached = _load_cached_summary(video_id)
        if cached:
            logger.info(f"Returning cached summary for {video_id}")
            return {"summary": cached, "cached": True}

    # Get all chunks from vector store
    chunks = vector_store.get_all_chunks(video_id)
    if not chunks:
        return {
            "summary": "No transcript data available to summarize.",
            "cached": False,
        }

    # Combine all chunk texts
    full_text = "\n\n".join(
        f"[⏱ {c.get('metadata', {}).get('timestamp_display', '00:00')}] {c['text']}"
        for c in chunks
    )

    total_tokens = estimate_tokens(full_text)
    logger.info(f"Summary generation: {len(chunks)} chunks, ~{total_tokens} tokens")

    if total_tokens < 3000:
        # Short video: single-pass summary
        summary = _generate_short_summary(full_text)
    else:
        # Long video: hierarchical summarization
        summary = _generate_hierarchical_summary(chunks)

    # Cache the result
    _save_summary_cache(video_id, summary)

    return {"summary": summary, "cached": False}


def _generate_short_summary(transcript: str) -> str:
    """Generate a summary for a short transcript in a single LLM call."""
    prompt = SHORT_VIDEO_SUMMARY_PROMPT.format(transcript=transcript)
    return llm_service.generate_response(
        system_prompt="You are an expert video summarizer.",
        user_prompt=prompt,
    )


def _generate_hierarchical_summary(chunks: list[dict]) -> str:
    """
    Hierarchical summarization for long transcripts.

    Pipeline:
        1. Group chunks into sections (~5 chunks each)
        2. Summarize each section independently
        3. Combine section summaries into final structured summary
    """
    # Step 1: Group chunks into sections
    section_size = 5
    sections = []
    for i in range(0, len(chunks), section_size):
        section_chunks = chunks[i : i + section_size]
        section_text = "\n\n".join(
            f"[⏱ {c.get('metadata', {}).get('timestamp_display', '00:00')}] {c['text']}"
            for c in section_chunks
        )
        sections.append(section_text)

    logger.info(f"Hierarchical summary: {len(sections)} sections")

    # Step 2: Summarize each section
    section_summaries = []
    for i, section in enumerate(sections):
        logger.info(f"Summarizing section {i + 1}/{len(sections)}")
        prompt = SECTION_SUMMARY_PROMPT.format(section_text=section)
        section_summary = llm_service.generate_response(
            system_prompt="You are an expert summarizer.",
            user_prompt=prompt,
        )
        section_summaries.append(f"### Section {i + 1}\n{section_summary}")

    # Step 3: Combine into final summary
    combined = "\n\n".join(section_summaries)
    prompt = FINAL_SUMMARY_PROMPT.format(section_summaries=combined)
    final_summary = llm_service.generate_response(
        system_prompt="You are an expert video summarizer.",
        user_prompt=prompt,
    )

    return final_summary
