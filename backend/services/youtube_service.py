"""
YouTube URL parsing and validation service.
Handles extracting video IDs from various YouTube URL formats.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Regex patterns for YouTube URL formats
YOUTUBE_PATTERNS = [
    # Standard: https://www.youtube.com/watch?v=VIDEO_ID
    re.compile(
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})"
    ),
    # Short: https://youtu.be/VIDEO_ID
    re.compile(
        r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})"
    ),
    # Embed: https://www.youtube.com/embed/VIDEO_ID
    re.compile(
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})"
    ),
    # Shorts: https://www.youtube.com/shorts/VIDEO_ID
    re.compile(
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})"
    ),
]


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract the 11-character YouTube video ID from a URL.

    Supports:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        - https://www.youtube.com/shorts/VIDEO_ID

    Returns:
        The video ID string, or None if the URL is invalid.
    """
    if not url or not isinstance(url, str):
        return None

    url = url.strip()

    for pattern in YOUTUBE_PATTERNS:
        match = pattern.search(url)
        if match:
            video_id = match.group(1)
            logger.info(f"Extracted video ID: {video_id} from URL: {url}")
            return video_id

    logger.warning(f"Could not extract video ID from URL: {url}")
    return None


def validate_youtube_url(url: str) -> tuple[bool, str]:
    """
    Validate a YouTube URL and return (is_valid, message).

    Returns:
        Tuple of (is_valid: bool, message: str)
    """
    if not url or not isinstance(url, str):
        return False, "Please provide a YouTube URL."

    url = url.strip()

    if not url.startswith(("http://", "https://", "youtube.com", "youtu.be", "www.youtube.com")):
        return False, "URL must be a valid YouTube link (e.g., https://www.youtube.com/watch?v=...)."

    video_id = extract_video_id(url)
    if not video_id:
        return False, "Could not find a valid YouTube video ID in this URL."

    return True, f"Valid YouTube URL. Video ID: {video_id}"


def build_video_url(video_id: str) -> str:
    """Build a canonical YouTube URL from a video ID."""
    return f"https://www.youtube.com/watch?v={video_id}"


def build_timestamp_url(video_id: str, seconds: float) -> str:
    """Build a YouTube URL that starts at a specific timestamp."""
    t = int(seconds)
    return f"https://www.youtube.com/watch?v={video_id}&t={t}s"
