"""
Application configuration using Pydantic Settings.
Loads values from .env file with sensible defaults.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- LLM Configuration ---
    # Providers are tried in order: Groq primary → Groq fallback model → Gemini.
    # Groq limits are per model, so a second Groq model doubles the free daily quota.
    # Any provider without an API key is skipped.
    LLM_API_KEY: str = Field(default="", description="Groq API key")
    LLM_MODEL: str = Field(
        default="qwen/qwen3.8-27b",
        description="Primary Groq model",
    )
    LLM_FALLBACK_MODEL: str = Field(
        default="openai/gpt-oss-120b",
        description="Second Groq model (separate rate-limit bucket). Empty to disable.",
    )
    GEMINI_API_KEY: str = Field(default="", description="Google AI Studio API key (optional fallback)")
    GEMINI_MODEL: str = Field(default="gemini-3.5-flash-lite", description="Gemini fallback model")
    LLM_TEMPERATURE: float = Field(default=0.1, description="LLM temperature")
    LLM_MAX_TOKENS: int = Field(default=4096, description="Max tokens per LLM response")

    # --- Embedding Model ---
    EMBEDDING_MODEL: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="FastEmbed model (ONNX, runs locally on CPU)",
    )
    EMBEDDING_CACHE_DIR: str = Field(default="./.model_cache", description="FastEmbed model cache")

    # --- Vector Database (Qdrant) ---
    # Set QDRANT_URL + QDRANT_API_KEY for Qdrant Cloud. If QDRANT_URL is empty,
    # an embedded local Qdrant is stored at QDRANT_PATH (good for local runs).
    QDRANT_URL: str = Field(default="", description="Qdrant Cloud cluster URL")
    QDRANT_API_KEY: str = Field(default="", description="Qdrant Cloud API key")
    QDRANT_PATH: str = Field(default="./qdrant_data", description="Local Qdrant storage path")

    # --- RAG Settings ---
    TOP_K: int = Field(default=5, description="Number of chunks to retrieve")
    CHUNK_SIZE: int = Field(default=1000, description="Chunk size in characters")
    CHUNK_OVERLAP: int = Field(default=200, description="Chunk overlap in characters")

    # --- Limits ---
    MAX_VIDEO_DURATION_MINUTES: int = Field(
        default=120,
        description="Maximum video duration in minutes",
    )
    MAX_CONVERSATION_HISTORY: int = Field(
        default=6,
        description="Max conversation turns to keep in Q&A context",
    )
    MAX_PASTED_TRANSCRIPT_CHARS: int = Field(
        default=300_000,
        description="Max size of a pasted transcript",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Returns cached application settings singleton."""
    return Settings()
