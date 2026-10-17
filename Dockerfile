FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    EMBEDDING_CACHE_DIR=/app/.model_cache

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the embedding model at build time so cold starts don't fetch it
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2', cache_dir='/app/.model_cache')"

# Copy application code
COPY backend/ backend/
COPY frontend/ frontend/

EXPOSE 8000

# Render provides $PORT; default to 8000 for local Docker runs
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
