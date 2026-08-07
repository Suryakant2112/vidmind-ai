"""
VidMind AI — FastAPI Application Entry Point.

Serves:
- REST API at /api/*
- Static frontend files at /
"""

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as api_router
from backend.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    settings = get_settings()
    logger.info("=" * 60)
    logger.info("VidMind AI — Starting up")
    logger.info(f"  LLM Model:     {settings.LLM_MODEL}")
    logger.info(f"  Embedding:     {settings.EMBEDDING_MODEL}")
    logger.info(f"  ChromaDB:      {settings.CHROMA_DB_PATH}")
    logger.info(f"  Chunk Size:    {settings.CHUNK_SIZE}")
    logger.info(f"  Top-K:         {settings.TOP_K}")
    logger.info(f"  Max Duration:  {settings.MAX_VIDEO_DURATION_MINUTES} min")
    logger.info("=" * 60)

    # Create storage directories
    os.makedirs(settings.CHROMA_DB_PATH, exist_ok=True)
    os.makedirs(settings.CACHE_DIR, exist_ok=True)

    yield

    # Shutdown
    logger.info("VidMind AI — Shutting down")


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="VidMind AI",
    description="AI-powered YouTube video summarizer, lecture notes generator, and Q&A assistant.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend to communicate with API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Return empty 204 response for favicon requests."""
    return Response(status_code=204)


@app.get("/")
async def serve_frontend():
    """Serve the main frontend page."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "VidMind AI API is running. Frontend not found."}


# =============================================================================
# Run with: uvicorn backend.main:app --reload
# =============================================================================
