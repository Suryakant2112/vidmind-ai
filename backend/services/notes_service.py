"""
AI lecture notes generation service.
Uses hierarchical generation for long transcripts:
    Full Transcript → Chunk Notes → Section Notes → Final Structured Notes

The notes are fundamentally different from the summary:
- Summary: "What is this video about?"
- Notes: "What should I write down and study from this lecture?"
"""

import json
import os
import logging
from typing import Optional

from backend.config import get_settings
from backend.services import vector_store, llm_service
from backend.utils.helpers import estimate_tokens

logger = logging.getLogger(__name__)

# =============================================================================
# Prompts
# =============================================================================

CHUNK_NOTES_PROMPT = """You are an expert academic note-taker. Create detailed study notes from this section of a lecture transcript.

RULES:
- Extract ALL important information: definitions, concepts, examples, formulas, processes, comparisons.
- Do NOT invent or fabricate any information not present in the text.
- If the section mentions a formula, preserve it exactly.
- If examples are given, include them.
- If no formulas or examples are present, do NOT create them.
- Use clear academic note format with headings, bullet points, and bold terms.
- Include the timestamp using ⏱ MM:SS format.
- Focus on what a student should write down and study.

TRANSCRIPT SECTION:
{chunk_text}
"""

SECTION_MERGE_PROMPT = """You are an expert academic note-taker. Below are detailed notes from consecutive sections of a lecture.

Merge and organize these into well-structured study notes for this topic/section.

RULES:
- Combine related points. Remove redundancy.
- Maintain ALL important details: definitions, examples, formulas, key terms.
- Do NOT add any information not present in the source notes.
- Use clear academic structure with headings and sub-headings.
- Preserve timestamps (⏱ MM:SS format).
- Focus on creating notes that are optimal for studying and review.

FORMAT:
## [Topic/Concept Name]

### Definition
...

### Key Points
- Point 1
- Point 2

### Examples (if any in the source)
...

### Important Terms
- **Term**: definition

### Timestamp
⏱ MM:SS

SOURCE NOTES:
{section_notes}
"""

FINAL_NOTES_PROMPT = """You are an expert academic note-taker creating comprehensive lecture notes from a YouTube lecture.

Below are organized notes from different sections of the lecture. Create the FINAL, complete set of lecture notes.

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

# [Lecture Title — infer from content]

## 1. [First Major Topic]

### Definition
Clear definition of the concept.

### Explanation
Detailed explanation from the lecture.

### Key Points
- Important point 1
- Important point 2
- Important point 3

### Examples
(Only if examples were provided in the lecture)

### Important Terms
- **Term 1**: Definition
- **Term 2**: Definition

### Formula / Equation
(Only if formulas were discussed in the lecture)

⏱ MM:SS

---

## 2. [Second Major Topic]
(Same structure as above)

---

(Continue for all major topics...)

---

## Key Takeaways
1. Most important lesson 1
2. Most important lesson 2
3. Most important lesson 3

## Important Timestamps
- ⏱ MM:SS — Topic/concept discussed at this point
- ⏱ MM:SS — Topic/concept discussed at this point

STRICT RULES:
- Use ONLY information from the section notes below.
- Do NOT invent definitions, formulas, examples, or claims not in the source.
- If the lecture doesn't cover formulas, do NOT include a Formula section.
- Preserve ALL technical terminology exactly as used in the lecture.
- Make notes scannable: use headings, bullet points, bold terms.
- These notes should be what a diligent student would write down during the lecture.

SECTION NOTES:
{all_section_notes}
"""

SHORT_VIDEO_NOTES_PROMPT = """You are an expert academic note-taker. Create detailed, comprehensive lecture notes from this YouTube video transcript.

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

# [Lecture Title — infer from content]

## 1. [First Major Topic]

### Definition
Clear definition if provided in the transcript.

### Explanation
Detailed explanation from the lecture.

### Key Points
- Important point 1
- Important point 2

### Examples
(Only include if examples are actually in the transcript)

### Important Terms
- **Term**: Definition

⏱ MM:SS

---

## 2. [Second Major Topic]
(Same structure)

---

## Key Takeaways
1. Takeaway 1
2. Takeaway 2

## Important Timestamps
- ⏱ MM:SS — Description

STRICT RULES:
- Use ONLY the transcript content. Do NOT fabricate information.
- Do NOT invent formulas, definitions, or examples not in the transcript.
- Preserve technical terminology exactly.
- Include timestamps (⏱ MM:SS) for each major section.
- Focus on what a student should study and remember.

TRANSCRIPT:
{transcript}
"""


# =============================================================================
# Caching
# =============================================================================

def _get_cache_path(video_id: str) -> str:
    """Get the cache file path for a video's notes."""
    settings = get_settings()
    cache_dir = os.path.join(settings.CACHE_DIR, video_id)
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "notes.json")


def _load_cached_notes(video_id: str) -> Optional[str]:
    """Load cached notes if available."""
    path = _get_cache_path(video_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("notes")
        except Exception:
            pass
    return None


def _save_notes_cache(video_id: str, notes: str) -> None:
    """Save generated notes to cache."""
    path = _get_cache_path(video_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"video_id": video_id, "notes": notes}, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to cache notes: {e}")


# =============================================================================
# Notes Generation
# =============================================================================

def generate_notes(video_id: str, force_regenerate: bool = False) -> dict:
    """
    Generate detailed AI lecture notes for a processed video.

    Uses hierarchical generation for long transcripts:
        1. Generate chunk-level notes
        2. Merge into section-level notes
        3. Produce final structured lecture notes

    Short transcripts are handled in a single pass.

    Args:
        video_id: YouTube video ID
        force_regenerate: If True, ignore cache

    Returns:
        Dict with 'notes' (markdown string) and 'cached' (bool)
    """
    # Check cache first
    if not force_regenerate:
        cached = _load_cached_notes(video_id)
        if cached:
            logger.info(f"Returning cached notes for {video_id}")
            return {"notes": cached, "cached": True}

    # Get all chunks from vector store
    chunks = vector_store.get_all_chunks(video_id)
    if not chunks:
        return {
            "notes": "No transcript data available to generate notes.",
            "cached": False,
        }

    # Combine all chunk texts with timestamps
    full_text = "\n\n".join(
        f"[⏱ {c.get('metadata', {}).get('timestamp_display', '00:00')}] {c['text']}"
        for c in chunks
    )

    total_tokens = estimate_tokens(full_text)
    logger.info(f"Notes generation: {len(chunks)} chunks, ~{total_tokens} tokens")

    if total_tokens < 3000:
        # Short video: single-pass notes
        notes = _generate_short_notes(full_text)
    else:
        # Long video: hierarchical note generation
        notes = _generate_hierarchical_notes(chunks)

    # Cache the result
    _save_notes_cache(video_id, notes)

    return {"notes": notes, "cached": False}


def _generate_short_notes(transcript: str) -> str:
    """Generate notes for a short transcript in a single LLM call."""
    prompt = SHORT_VIDEO_NOTES_PROMPT.format(transcript=transcript)
    return llm_service.generate_response(
        system_prompt="You are an expert academic note-taker creating study material.",
        user_prompt=prompt,
    )


def _generate_hierarchical_notes(chunks: list[dict]) -> str:
    """
    Hierarchical note generation for long transcripts.

    Pipeline:
        1. Generate chunk-level notes (each chunk → detailed notes)
        2. Group into sections and merge
        3. Combine into final structured lecture notes
    """
    # Step 1: Generate notes for each chunk (or small groups)
    chunk_group_size = 3  # Process 3 chunks at a time
    chunk_notes = []

    for i in range(0, len(chunks), chunk_group_size):
        group = chunks[i : i + chunk_group_size]
        group_text = "\n\n".join(
            f"[⏱ {c.get('metadata', {}).get('timestamp_display', '00:00')}] {c['text']}"
            for c in group
        )

        logger.info(
            f"Generating chunk notes {i // chunk_group_size + 1}/"
            f"{(len(chunks) + chunk_group_size - 1) // chunk_group_size}"
        )

        prompt = CHUNK_NOTES_PROMPT.format(chunk_text=group_text)
        notes = llm_service.generate_response(
            system_prompt="You are an expert academic note-taker.",
            user_prompt=prompt,
        )
        chunk_notes.append(notes)

    # Step 2: Merge chunk notes into section notes
    # Group every 3-4 chunk notes into a section
    section_group_size = 4
    section_notes = []

    if len(chunk_notes) <= section_group_size:
        # Few enough to go directly to final
        section_notes = chunk_notes
    else:
        for i in range(0, len(chunk_notes), section_group_size):
            group = chunk_notes[i : i + section_group_size]
            combined = "\n\n---\n\n".join(group)

            logger.info(
                f"Merging section {i // section_group_size + 1}/"
                f"{(len(chunk_notes) + section_group_size - 1) // section_group_size}"
            )

            prompt = SECTION_MERGE_PROMPT.format(section_notes=combined)
            merged = llm_service.generate_response(
                system_prompt="You are an expert academic note-taker.",
                user_prompt=prompt,
            )
            section_notes.append(merged)

    # Step 3: Final structured notes
    all_sections = "\n\n---\n\n".join(section_notes)
    prompt = FINAL_NOTES_PROMPT.format(all_section_notes=all_sections)
    final_notes = llm_service.generate_response(
        system_prompt="You are an expert academic note-taker creating comprehensive study material.",
        user_prompt=prompt,
    )

    return final_notes
