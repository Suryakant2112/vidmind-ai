"""
FastAPI API routes for VidMind AI.
"""

import logging
from fastapi import APIRouter, HTTPException

from backend.config import get_settings
from backend.models.schemas import (
    VideoProcessRequest,
    VideoProcessResponse,
    VideoInfo,
    SummaryResponse,
    NotesResponse,
    QuestionRequest,
    AnswerResponse,
    HealthResponse,
    ProcessingStep,
    ErrorResponse,
)
from backend.services import (
    youtube_service,
    transcript_service,
    chunking_service,
    vector_store,
    summary_service,
    notes_service,
    rag_service,
)
from backend.utils.helpers import format_duration

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["api"])

# In-memory metadata store for processed videos
# In production, this would be a database
_video_metadata: dict[str, dict] = {}


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        services={
            "api": "running",
            "vector_store": "chromadb",
            "embeddings": "sentence-transformers (local)",
            "llm": "groq (external api)",
        },
    )


# =============================================================================
# Video Processing
# =============================================================================

@router.post("/video/process", response_model=VideoProcessResponse)
async def process_video(request: VideoProcessRequest):
    """
    Process a YouTube video: extract transcript, chunk, embed, and store.

    This is the main entry point. After processing, the video is ready
    for summary generation, note generation, and Q&A.
    """
    steps = []
    video_id = None

    try:
        # Step 1: Validate URL and extract video ID
        steps.append(ProcessingStep(step="Validating YouTube URL", status="in_progress"))
        is_valid, message = youtube_service.validate_youtube_url(request.url)
        if not is_valid:
            steps[-1].status = "error"
            steps[-1].message = message
            raise HTTPException(status_code=400, detail=message)

        video_id = youtube_service.extract_video_id(request.url)
        video_url = youtube_service.build_video_url(video_id)
        steps[-1].status = "done"
        steps[-1].message = f"Video ID: {video_id}"

        # Step 2: Check if already processed
        steps.append(ProcessingStep(step="Checking existing data", status="in_progress"))
        if vector_store.video_exists(video_id):
            steps[-1].status = "done"
            steps[-1].message = "Video already processed — loading existing data"

            # Return cached info
            info = _video_metadata.get(video_id, {})
            return VideoProcessResponse(
                success=True,
                video_info=VideoInfo(
                    video_id=video_id,
                    video_url=video_url,
                    title=info.get("title", ""),
                    duration_seconds=info.get("duration_seconds", 0),
                    transcript_segments=info.get("transcript_segments", 0),
                    chunk_count=vector_store.get_chunk_count(video_id),
                    is_processed=True,
                ),
                message="Video already processed. Ready for Summary, Notes, and Q&A.",
                steps=steps,
            )
        steps[-1].status = "done"
        steps[-1].message = "New video — processing required"

        # Step 3: Extract transcript
        steps.append(ProcessingStep(step="Extracting transcript", status="in_progress"))
        segments, transcript_msg = transcript_service.fetch_transcript(video_id)
        if segments is None:
            steps[-1].status = "error"
            steps[-1].message = transcript_msg
            raise HTTPException(status_code=400, detail=transcript_msg)
        steps[-1].status = "done"
        steps[-1].message = f"{len(segments)} segments extracted"

        # Step 4: Check duration limit
        duration = transcript_service.get_transcript_duration(segments)
        settings = get_settings()
        max_duration = settings.MAX_VIDEO_DURATION_MINUTES * 60
        if duration > max_duration:
            msg = (
                f"Video is too long ({format_duration(duration)}). "
                f"Maximum supported duration is {settings.MAX_VIDEO_DURATION_MINUTES} minutes."
            )
            raise HTTPException(status_code=400, detail=msg)

        # Step 5: Clean transcript
        steps.append(ProcessingStep(step="Cleaning transcript", status="in_progress"))
        cleaned_segments = transcript_service.clean_transcript(segments)
        if not cleaned_segments:
            raise HTTPException(status_code=400, detail="Transcript is empty after cleaning.")
        steps[-1].status = "done"
        steps[-1].message = f"{len(cleaned_segments)} segments after cleaning"

        # Step 6: Chunk transcript
        steps.append(ProcessingStep(step="Creating semantic chunks", status="in_progress"))
        chunks = chunking_service.chunk_transcript(
            segments=cleaned_segments,
            video_id=video_id,
            video_url=video_url,
        )
        if not chunks:
            raise HTTPException(status_code=500, detail="Failed to create transcript chunks.")
        steps[-1].status = "done"
        steps[-1].message = f"{len(chunks)} chunks created"

        # Step 7: Generate embeddings and store in ChromaDB
        steps.append(ProcessingStep(
            step="Generating embeddings & storing in vector database",
            status="in_progress",
        ))
        stored_count = vector_store.store_chunks(video_id, chunks)
        steps[-1].status = "done"
        steps[-1].message = f"{stored_count} chunks embedded and stored"

        # Step 8: Done
        steps.append(ProcessingStep(step="Video ready", status="done", message="✓"))

        # Save metadata
        _video_metadata[video_id] = {
            "title": "",  # Could be fetched via YouTube Data API if needed
            "duration_seconds": duration,
            "transcript_segments": len(segments),
            "chunk_count": len(chunks),
        }

        return VideoProcessResponse(
            success=True,
            video_info=VideoInfo(
                video_id=video_id,
                video_url=video_url,
                duration_seconds=duration,
                transcript_segments=len(segments),
                chunk_count=len(chunks),
                is_processed=True,
            ),
            message="Video processed successfully! Ready for Summary, Notes, and Q&A.",
            steps=steps,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video processing failed: {e}", exc_info=True)
        if steps and steps[-1].status == "in_progress":
            steps[-1].status = "error"
            steps[-1].message = str(e)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


# =============================================================================
# Video Info
# =============================================================================

@router.get("/video/{video_id}")
async def get_video_info(video_id: str):
    """Get metadata for a processed video."""
    if not vector_store.video_exists(video_id):
        raise HTTPException(status_code=404, detail="Video not found. Please process it first.")

    info = _video_metadata.get(video_id, {})
    return VideoInfo(
        video_id=video_id,
        video_url=youtube_service.build_video_url(video_id),
        title=info.get("title", ""),
        duration_seconds=info.get("duration_seconds", 0),
        transcript_segments=info.get("transcript_segments", 0),
        chunk_count=vector_store.get_chunk_count(video_id),
        is_processed=True,
    )


# =============================================================================
# Summary
# =============================================================================

@router.get("/video/{video_id}/summary", response_model=SummaryResponse)
async def get_summary(video_id: str):
    """
    Generate or retrieve an AI summary of the video.
    Uses hierarchical summarization for long transcripts.
    """
    if not vector_store.video_exists(video_id):
        raise HTTPException(status_code=404, detail="Video not found. Please process it first.")

    try:
        result = summary_service.generate_summary(video_id)
        return SummaryResponse(
            video_id=video_id,
            summary=result["summary"],
            cached=result.get("cached", False),
        )
    except Exception as e:
        logger.error(f"Summary generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Lecture Notes
# =============================================================================

@router.get("/video/{video_id}/notes", response_model=NotesResponse)
async def get_notes(video_id: str):
    """
    Generate or retrieve detailed AI lecture notes.
    Uses hierarchical generation for long transcripts.
    """
    if not vector_store.video_exists(video_id):
        raise HTTPException(status_code=404, detail="Video not found. Please process it first.")

    try:
        result = notes_service.generate_notes(video_id)
        return NotesResponse(
            video_id=video_id,
            notes=result["notes"],
            cached=result.get("cached", False),
        )
    except Exception as e:
        logger.error(f"Notes generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Ask AI (RAG Q&A)
# =============================================================================

@router.post("/video/{video_id}/ask", response_model=AnswerResponse)
async def ask_question(video_id: str, request: QuestionRequest):
    """
    Ask a question about the video using RAG.

    Pipeline: Question → Embed → Retrieve → Context → LLM → Grounded Answer
    """
    if not vector_store.video_exists(video_id):
        raise HTTPException(status_code=404, detail="Video not found. Please process it first.")

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Please enter a question.")

    try:
        result = rag_service.ask_question(
            video_id=video_id,
            question=request.question.strip(),
            conversation_history=request.conversation_history,
        )
        return AnswerResponse(
            video_id=video_id,
            question=result["question"],
            answer=result["answer"],
            sources=result.get("sources", []),
        )
    except Exception as e:
        logger.error(f"Q&A failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
