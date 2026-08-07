# """
# Application configuration using Pydantic Settings.
# Loads values from .env file with sensible defaults.
# """

# from pydantic_settings import BaseSettings
# from pydantic import Field
# from functools import lru_cache


# class Settings(BaseSettings):
#     """Application settings loaded from environment variables."""

#     # --- LLM Configuration ---
#     LLM_API_KEY: str = Field(default="", description="Groq API key")
#     LLM_MODEL: str = Field(
#         default="llama-3.3-70b-versatile",
#         description="LLM model name for Groq API",
#     )
#     LLM_TEMPERATURE: float = Field(default=0.1, description="LLM temperature")
#     LLM_MAX_TOKENS: int = Field(default=4096, description="Max tokens per LLM response")

#     # --- Embedding Model ---
#     EMBEDDING_MODEL: str = Field(
#         default="sentence-transformers/all-MiniLM-L6-v2",
#         description="Sentence Transformer model (runs locally on CPU)",
#     )

#     # --- RAG Settings ---
#     TOP_K: int = Field(default=5, description="Number of chunks to retrieve")
#     CHUNK_SIZE: int = Field(default=1000, description="Chunk size in characters")
#     CHUNK_OVERLAP: int = Field(default=200, description="Chunk overlap in characters")

#     # --- Limits ---
#     MAX_VIDEO_DURATION_MINUTES: int = Field(
#         default=120,
#         description="Maximum video duration in minutes",
#     )
#     MAX_CONVERSATION_HISTORY: int = Field(
#         default=6,
#         description="Max conversation turns to keep in Q&A context",
#     )

#     # --- Storage ---
#     CHROMA_DB_PATH: str = Field(default="./chroma_db", description="ChromaDB storage path")
#     CACHE_DIR: str = Field(default="./cache", description="Cache directory for summaries/notes")

#     model_config = {
#         "env_file": ".env",
#         "env_file_encoding": "utf-8",
#         "case_sensitive": True,
#     }


# @lru_cache()
# def get_settings() -> Settings:
#     """Returns cached application settings singleton."""
#     return Settings()


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
    LLM_API_KEY: str = Field(default="", description="Groq API key")
    LLM_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="LLM model name for Groq API",
    )
    LLM_TEMPERATURE: float = Field(default=0.1, description="LLM temperature")
    LLM_MAX_TOKENS: int = Field(default=4096, description="Max tokens per LLM response")

    # --- Embedding Model ---
    EMBEDDING_MODEL: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Sentence Transformer model (runs locally on CPU)",
    )

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

    # --- Storage ---
    CHROMA_DB_PATH: str = Field(default="./chroma_db", description="ChromaDB storage path")
    CACHE_DIR: str = Field(default="./cache", description="Cache directory for summaries/notes")

    # --- YouTube Cookie (for cloud deployment) ---
    COOKIE_PATH: str = Field(
        default="",
        description="Path to cookies.txt file to bypass YouTube IP blocks on cloud providers",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """Returns cached application settings singleton."""
    return Settings()

