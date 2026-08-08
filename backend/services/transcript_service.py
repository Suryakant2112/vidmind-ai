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
        # --- 1. Primary Method: External API (Supadata) ---
        # Bypasses IP blocks on cloud providers like Render
        from backend.config import get_settings
        settings = get_settings()

        if settings.SUPADATA_API_KEY:
            logger.info(f"Attempting to fetch transcript for {video_id} using Supadata API...")
            try:
                import httpx
                url = f"https://www.youtube.com/watch?v={video_id}"
                response = httpx.get(
                    f"https://api.supadata.ai/v1/youtube/transcript?url={url}",
                    headers={"x-api-key": settings.SUPADATA_API_KEY},
                    timeout=15.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("content", [])
                    
                    if content:
                        result = []
                        for seg in content:
                            result.append({
                                "text": seg.get("text", ""),
                                "start": float(seg.get("offset", 0)) / 1000.0,
                                "duration": float(seg.get("duration", 0)) / 1000.0,
                            })
                        
                        logger.info(f"Successfully extracted {len(result)} segments using Supadata API")
                        return result, f"Transcript fetched via API: {len(result)} segments"
                
                logger.warning(f"Supadata API failed. Status: {response.status_code}. Falling back to local extractors...")
            except Exception as api_e:
                logger.warning(f"Supadata API request error: {api_e}. Falling back to local extractors...")

        # --- 2. Fallback Method 1: youtube-transcript-api ---
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
        logger.warning(f"youtube-transcript-api failed for {video_id}: {error_msg}")

        # --- yt-dlp Fallback ---
        # If blocked by YouTube, yt-dlp is often more resilient. We use it to fetch the auto-captions JSON.
        logger.info(f"Attempting yt-dlp fallback for {video_id}...")
        try:
            import subprocess
            import json
            
            # Use yt-dlp to dump video info including subtitles, but skip downloading the actual video
            cmd = [
                "yt-dlp",
                "--dump-json",
                "--skip-download",
                f"https://www.youtube.com/watch?v={video_id}"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            video_info = json.loads(result.stdout)
            
            # YouTube stores auto-generated subtitles in 'automatic_captions' (or 'subtitles' for manual)
            captions = video_info.get("automatic_captions", {})
            if not captions:
                captions = video_info.get("subtitles", {})
                
            if "en" in captions:
                # Find the json3 format url (which contains precise timestamps)
                json3_url = next((fmt["url"] for fmt in captions["en"] if fmt.get("ext") == "json3"), None)
                
                if json3_url:
                    import urllib.request
                    req = urllib.request.Request(json3_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response:
                        json3_data = json.loads(response.read().decode())
                        
                        segments = []
                        for event in json3_data.get("events", []):
                            if "segs" in event:
                                text = "".join(seg.get("utf8", "") for seg in event["segs"])
                                if text.strip():
                                    segments.append({
                                        "text": text,
                                        "start": float(event.get("tStartMs", 0)) / 1000.0,
                                        "duration": float(event.get("dDurationMs", 0)) / 1000.0 if "dDurationMs" in event else 0.0
                                    })
                        
                        if segments:
                            logger.info(f"Successfully extracted {len(segments)} segments using yt-dlp fallback")
                            return segments, f"Transcript fetched via fallback: {len(segments)} segments"
            
            logger.error("yt-dlp fallback failed to find English json3 subtitles.")
        except Exception as yt_e:
            logger.error(f"yt-dlp fallback also failed: {yt_e}")

        # If fallback also fails, report the original error
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
