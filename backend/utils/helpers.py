"""
Utility functions for timestamp formatting, URL building, and text processing.
"""

import re
import math


def seconds_to_timestamp(seconds: float) -> str:
    """
    Convert seconds to a human-readable timestamp.

    Examples:
        65.5  -> "01:05"
        3661  -> "1:01:01"
    """
    total_seconds = int(math.floor(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def timestamp_to_youtube_url(video_id: str, seconds: float) -> str:
    """
    Build a clickable YouTube URL that starts at a specific timestamp.

    Example:
        ("dQw4w9WgXcQ", 120.5) -> "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120s"
    """
    t = int(math.floor(seconds))
    return f"https://www.youtube.com/watch?v={video_id}&t={t}s"


def sanitize_input(text: str) -> str:
    """Basic input sanitization — strips dangerous characters."""
    if not text:
        return ""
    # Remove null bytes and control characters (keep newlines and tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text.strip()


def estimate_tokens(text: str) -> int:
    """
    Rough token estimate (~4 chars per token for English).
    Used for context-window management, not billing.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds to a readable string.

    Examples:
        65    -> "1m 5s"
        3661  -> "1h 1m 1s"
    """
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def clean_markdown(text: str) -> str:
    """Light cleanup of LLM-generated markdown."""
    if not text:
        return ""
    # Remove excessive blank lines (keep max 2)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()
