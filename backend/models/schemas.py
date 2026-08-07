"""
Pydantic request/response models for the VidMind AI API.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional


# =============================================================================
# Request Models
# =============================================================================

class VideoProcessRequest(BaseModel):
    """Request to process a YouTube video."""
    url: str = Field(..., description="YouTube video URL", min_length=10)


class QuestionRequest(BaseModel):
    """Request to ask a question about a video."""
    question: str = Field(..., description="User question", min_length=1, max_length=2000)
    conversation_history: list[dict] = Field(
        default_factory=list,
        description="Previous conversation turns [{role, content}]",
    )


# =============================================================================
# Response Models
# =============================================================================

class SourceTimestamp(BaseModel):
    """A timestamp source reference."""
    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(0.0, description="End time in seconds")
    text_preview: str = Field("", description="Short preview of the source chunk")
    timestamp_display: str = Field("", description="Formatted timestamp e.g. '18:42'")
    youtube_url: str = Field("", description="YouTube URL with timestamp parameter")


class ProcessingStep(BaseModel):
    """A single processing step with status."""
    step: str
    status: str = "pending"  # pending | in_progress | done | error
    message: str = ""


class VideoInfo(BaseModel):
    """Metadata about a processed video."""
    video_id: str
    video_url: str
    title: str = ""
    duration_seconds: float = 0.0
    transcript_segments: int = 0
    chunk_count: int = 0
    is_processed: bool = False


class VideoProcessResponse(BaseModel):
    """Response after processing a video."""
    success: bool
    video_info: VideoInfo
    message: str = ""
    steps: list[ProcessingStep] = []


class SummaryResponse(BaseModel):
    """AI-generated video summary."""
    video_id: str
    summary: str  # Markdown-formatted summary
    cached: bool = False
    sources: list[SourceTimestamp] = []


class NotesResponse(BaseModel):
    """AI-generated lecture notes."""
    video_id: str
    notes: str  # Markdown-formatted lecture notes
    cached: bool = False
    sources: list[SourceTimestamp] = []


class AnswerResponse(BaseModel):
    """RAG-grounded answer to a question."""
    video_id: str
    question: str
    answer: str
    sources: list[SourceTimestamp] = []


class ErrorResponse(BaseModel):
    """Standardized error response."""
    error: str
    detail: str = ""


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = "1.0.0"
    services: dict = {}
