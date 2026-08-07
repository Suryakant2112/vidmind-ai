"""
Transcript extraction and cleaning service.
Fetches YouTube transcripts with timestamps and cleans the text.
"""

import re
import logging
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger(__name__)


# Transcript artifacts to remove (common auto-generated noise)
NOISE_PATTERNS = [
    re.compile(r"\[Music\]", re.IGNORECASE),
    re.compile(r"\[Applause\]", re.IGNORECASE),
    re.compile(r"\[Laughter\]", re.IGNORECASE),
    re.compile(r"\[音楽\]", re.IGNORECASE),  # Japanese [Music]
    re.compile(r"^\s*$"),  # Empty lines
]


def fetch_transcript(video_id: str) -> tuple[Optional[list[dict]], str]:
    """
    Fetch the transcript for a YouTube video.

    Prefers manually created transcripts over auto-generated ones.

    Args:
        video_id: YouTube video ID (11 characters)

    Returns:
        Tuple of (transcript_segments, status_message)
        Each segment: {"text": str, "start": float, "duration": float}
    """
    try:
        # Support both newer instance-based YouTubeTranscriptApi and legacy classmethods
        try:
            ytt = YouTubeTranscriptApi()
            transcript_list = ytt.list(video_id)
        except (AttributeError, TypeError):
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Prefer manually created transcripts
        transcript = None
        try:
            transcript = transcript_list.find_manually_created_transcript(["en"])
            logger.info(f"Found manually created English transcript for {video_id}")
        except Exception:
            pass

        if transcript is None:
            try:
                transcript = transcript_list.find_generated_transcript(["en"])
                logger.info(f"Found auto-generated English transcript for {video_id}")
            except Exception:
                pass

        # If no English transcript, try any available language
        if transcript is None:
            try:
                available = list(transcript_list)
                if available:
                    transcript = available[0]
                    logger.info(
                        f"Using {transcript.language} transcript for {video_id}"
                    )
            except Exception:
                pass

        if transcript is None:
            return None, "No transcript available for this video."

        raw_segments = transcript.fetch()

        if not raw_segments:
            return None, "Transcript is empty."

        # Convert to list of dicts (normalize format across API versions)
        result = []
        for seg in raw_segments:
            if isinstance(seg, dict):
                text = seg.get("text", "")
                start = seg.get("start", 0.0)
                duration = seg.get("duration", 0.0)
            else:
                text = getattr(seg, "text", str(seg))
                start = getattr(seg, "start", 0.0)
                duration = getattr(seg, "duration", 0.0)

            result.append({
                "text": str(text),
                "start": float(start),
                "duration": float(duration),
            })

        logger.info(f"Fetched {len(result)} transcript segments for {video_id}")
        return result, f"Transcript fetched: {len(result)} segments"

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Transcript extraction failed for {video_id}: {error_msg}")

        if "disabled" in error_msg.lower():
            return None, "Transcripts are disabled for this video."
        elif "no transcript" in error_msg.lower() or "not found" in error_msg.lower():
            return None, "No transcript available for this video. The video may not have captions."
        elif "video unavailable" in error_msg.lower() or "not exist" in error_msg.lower():
            return None, "This video is unavailable or does not exist."
        else:
            return None, f"Failed to extract transcript: {error_msg}"


def clean_transcript(segments: list[dict]) -> list[dict]:
    """
    Clean transcript segments while preserving timestamps and meaningful content.

    Handles:
        - Repeated whitespace
        - [Music], [Applause] and similar artifacts
        - Duplicate adjacent segments
        - Empty segments

    Preserves:
        - Technical terms, definitions, formulas
        - Timestamps (start, duration)
    """
    cleaned = []
    prev_text = ""

    for segment in segments:
        text = segment.get("text", "")

        # Remove noise artifacts
        for pattern in NOISE_PATTERNS:
            text = pattern.sub("", text)

        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Skip empty segments
        if not text:
            continue

        # Skip exact duplicates of previous segment
        if text.lower() == prev_text.lower():
            continue

        cleaned.append({
            "text": text,
            "start": segment.get("start", 0.0),
            "duration": segment.get("duration", 0.0),
        })
        prev_text = text.lower()

    logger.info(
        f"Cleaned transcript: {len(segments)} -> {len(cleaned)} segments"
    )
    return cleaned


def get_transcript_full_text(segments: list[dict]) -> str:
    """Combine all transcript segments into a single text string."""
    return " ".join(seg["text"] for seg in segments)


def get_transcript_duration(segments: list[dict]) -> float:
    """Get the total duration of the transcript in seconds."""
    if not segments:
        return 0.0
    last = segments[-1]
    return last.get("start", 0.0) + last.get("duration", 0.0)
