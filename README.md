# VidMind AI — AI Video Summarizer, Lecture Notes & Q&A

An AI-powered learning assistant that transforms YouTube lectures into structured summaries, detailed study notes, and interactive Q&A — all grounded in the video's transcript using **Retrieval-Augmented Generation (RAG)**.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)
![LangChain](https://img.shields.io/badge/LangChain-0.3+-orange)
![ChromaDB](https://img.shields.io/badge/ChromaDB-1.0+-purple)

---

## 🎯 Features

- **🎬 YouTube Transcript Extraction** — Automatically fetches transcripts with timestamp preservation
- **📋 AI Video Summary** — Structured overview with main topics, key points, and takeaways
- **📝 AI Lecture Notes** — Detailed, study-optimized notes with definitions, formulas, and examples
- **💬 RAG-Based Q&A** — Ask questions grounded in the video's transcript
- **⏱ Timestamp Sources** — Clickable timestamps linking back to the exact moment in the video
- **🔄 Conversational Follow-ups** — Multi-turn Q&A with context awareness
- **🧠 Local Embeddings** — Sentence Transformers running on CPU (no paid API)
- **💾 Persistent Vector Storage** — ChromaDB with caching to avoid reprocessing
- **📊 Hierarchical Processing** — Long videos are processed in stages to handle context limits

---

## 🏗 Architecture

```text
                    USER
                     │
                     ↓
              YouTube Video URL
                     │
                     ↓
          ┌─────────────────────┐
          │ Transcript Extractor │  ← youtube-transcript-api (no API key)
          └──────────┬──────────┘
                     │
                     ↓
          Clean + Timestamped
             Transcript
                     │
                     ↓
          ┌─────────────────────┐
          │  Semantic Chunking   │  ← LangChain RecursiveCharacterTextSplitter
          └──────────┬──────────┘
                     │
                     ↓
          ┌─────────────────────┐
          │ Sentence Transformer │  ← all-MiniLM-L6-v2 (local, CPU)
          │     Embeddings       │
          └──────────┬──────────┘
                     │
                     ↓
          ┌─────────────────────┐
          │      ChromaDB        │  ← Persistent local vector database
          └──────────┬──────────┘
                     │
                     ↓
          ┌─────────────────────┐
          │   LangChain RAG      │  ← Retrieval + Prompt Engineering
          └──────────┬──────────┘
                     │
          ┌──────────┼──────────┐
          ↓          ↓          ↓
       SUMMARY      NOTES       Q&A
          │          │          │
          └──────────┼──────────┘
                     ↓
          ┌─────────────────────┐
          │   Groq LLM API       │  ← llama-3.3-70b-versatile (free tier)
          └──────────┬──────────┘
                     │
                     ↓
          Timestamped, Grounded
               Responses
```

### What Runs Locally (Free)

| Component | Technology | Cost |
|---|---|---|
| Transcript extraction | `youtube-transcript-api` | Free |
| Text cleaning & chunking | LangChain text splitters | Free |
| Embeddings | Sentence Transformers (`all-MiniLM-L6-v2`) | Free (CPU) |
| Vector database | ChromaDB (persistent local) | Free |
| RAG retrieval | ChromaDB similarity search | Free |
| Web server | FastAPI + Uvicorn | Free |

### What Uses External API (Free Tier)

| Component | Technology | Cost |
|---|---|---|
| LLM inference | Groq API (`llama-3.3-70b-versatile`) | Free tier (rate-limited) |

---

## 🛠 Tech Stack

| Layer | Technology | Role |
|---|---|---|
| **Backend** | FastAPI | REST API, async request handling |
| **LLM** | Groq (via `langchain-groq`) | Text generation for summaries, notes, Q&A |
| **Embeddings** | Sentence Transformers | Local vector embeddings (CPU) |
| **Vector DB** | ChromaDB | Persistent semantic search |
| **RAG** | LangChain | Prompt templates, chain composition |
| **Transcript** | `youtube-transcript-api` | YouTube transcript extraction |
| **Frontend** | HTML + CSS + JavaScript | Single-page application |
| **Config** | Pydantic Settings | Type-safe environment variables |

---

## 🔍 How RAG Works in This Project

### Question Answering

```text
User Question: "What is a vector database?"
         │
         ↓
   Question Embedding          ← Sentence Transformer (local)
         │
         ↓
   ChromaDB Similarity Search  ← Find top-K most relevant transcript chunks
         │
         ↓
   Context Construction         ← Combine retrieved chunks with timestamps
         │
         ↓
   LLM Prompt                  ← System prompt enforces grounding policy
         │
         ↓
   Groq API                    ← Generate answer using ONLY retrieved context
         │
         ↓
   Grounded Answer + Sources   ← Answer with clickable timestamp references
```

The LLM **never sees the full transcript**. It only receives the most relevant chunks retrieved via semantic search. This is what makes it RAG, not simple transcript → LLM.

### Grounding Policy

The system prompt strictly instructs the LLM to:
1. Use **only** the provided transcript context
2. **Never** fabricate information
3. Say "I couldn't find that information" when the context is insufficient
4. Cite timestamps when possible

---

## 📝 Lecture Notes Generation

For long videos, notes are generated hierarchically to avoid context-window overflow:

```text
Full Transcript
      ↓
Semantic Chunks (ChromaDB)
      ↓
Chunk-Level Notes              ← Each chunk → detailed study notes
      ↓
Section-Level Notes            ← Merge related chunk notes
      ↓
Final Structured Lecture Notes ← Comprehensive, organized study material
```

This pipeline ensures that even 2-hour lectures produce high-quality notes without losing detail.

---

## 🚀 Installation

### Prerequisites

- Python 3.11+
- A free Groq API key ([console.groq.com](https://console.groq.com))

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/youtube-rag.git
cd youtube-rag

# 2. Create a virtual environment
python -m venv venv

# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and add your Groq API key
```

### Environment Variables

```env
# Get a free key from https://console.groq.com
LLM_API_KEY=your_groq_api_key_here
LLM_MODEL=llama-3.3-70b-versatile

# Local embedding model (downloaded automatically, ~22MB)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# RAG settings
TOP_K=5
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Limits
MAX_VIDEO_DURATION_MINUTES=120
```

---

## ▶️ Running Locally

```bash
# Start the server
uvicorn backend.main:app --reload

# Open in browser
# http://localhost:8000
```

**First run**: The Sentence Transformer model (~22MB) will be downloaded automatically. This only happens once.

---

## 📡 API Documentation

FastAPI auto-generates interactive docs at `http://localhost:8000/docs`.

### Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/video/process` | POST | Process a YouTube video |
| `/api/video/{video_id}` | GET | Get video metadata |
| `/api/video/{video_id}/summary` | GET | Generate/retrieve AI summary |
| `/api/video/{video_id}/notes` | GET | Generate/retrieve lecture notes |
| `/api/video/{video_id}/ask` | POST | Ask a question (RAG Q&A) |

### Example: Process a Video

```bash
curl -X POST http://localhost:8000/api/video/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'
```

### Example: Ask a Question

```bash
curl -X POST http://localhost:8000/api/video/VIDEO_ID/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is RAG?", "conversation_history": []}'
```

---

## 📦 Deployment

### Docker

```bash
docker build -t youtube-rag .
docker run -p 8000:8000 --env-file .env youtube-rag
```

### Free Hosting Options

| Platform | Notes |
|---|---|
| **Render** | Free tier with 750 hours/month. May sleep after inactivity. |
| **Railway** | Free $5 credit/month. Good for demos. |
| **Fly.io** | Free tier with 3 shared VMs. |

**Important**: Free-tier hosting typically has:
- Limited RAM (512MB–1GB) — the embedding model needs ~200MB
- Cold starts after inactivity
- No persistent disk — ChromaDB data resets on restart
- CPU-only (which is fine for this project)

For persistent data on free tiers, consider using ChromaDB in ephemeral mode and re-processing videos on demand.

---

## 💡 Example Questions

After processing a video, try asking:

- "What are the main topics covered in this video?"
- "Explain the concept of [topic mentioned in the video]"
- "What examples were given for [concept]?"
- "What is the definition of [term] as discussed in the lecture?"
- "Summarize the section about [topic]"
- "What are the key differences between [A] and [B]?"

---

## ⚠️ Limitations

### Transcript Availability
- Not all YouTube videos have transcripts
- Auto-generated transcripts may contain errors
- Non-English videos may have limited transcript support

### Free-Tier API Limits
- Groq free tier has rate limits (requests per minute/day)
- Long videos require multiple LLM calls, consuming more of the rate limit
- If rate-limited, wait a moment and retry

### Content Accuracy
- Generated content is based on the transcript, which may have errors
- Auto-generated captions can misinterpret technical terms
- The LLM may occasionally misinterpret ambiguous transcript text

### Video Duration
- Default limit: 120 minutes (configurable)
- Very long videos (2+ hours) require many LLM calls for notes/summary
- Processing time increases with video length

### Free Hosting
- Ephemeral storage — processed data may be lost on restart
- Cold starts after inactivity periods
- Limited CPU/RAM

---

## 🔮 Future Improvements

- 🌐 Multilingual transcript support
- 📄 PDF export for lecture notes
- 🎴 Flashcard generation from notes
- 📊 Quiz generation from lecture content
- 🗣 Speaker identification/diarization
- 📋 Playlist batch processing
- 📑 Chapter detection from timestamps
- 🔍 Cross-video search across processed lectures
- 📱 Progressive Web App (PWA) support

---

## 📁 Project Structure

```text
youtube-rag/
├── backend/
│   ├── __init__.py
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Pydantic Settings
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py              # REST API endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── youtube_service.py     # URL parsing & validation
│   │   ├── transcript_service.py  # Transcript extraction & cleaning
│   │   ├── chunking_service.py    # Semantic chunking
│   │   ├── embedding_service.py   # Sentence Transformer embeddings
│   │   ├── vector_store.py        # ChromaDB abstraction
│   │   ├── llm_service.py         # Groq LLM integration
│   │   ├── rag_service.py         # RAG pipeline
│   │   ├── summary_service.py     # Hierarchical summarization
│   │   └── notes_service.py       # Hierarchical note generation
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py             # Pydantic request/response models
│   └── utils/
│       ├── __init__.py
│       └── helpers.py             # Utility functions
├── frontend/
│   ├── index.html                 # Single-page application
│   ├── style.css                  # Design system & styles
│   └── app.js                     # Frontend logic
├── chroma_db/                     # Persistent vector storage
├── cache/                         # Cached summaries & notes
├── .env.example                   # Environment variable template
├── .gitignore
├── requirements.txt
├── Dockerfile
└── README.md
```

---

##  Screenshots 
Upload page - <img width="1280" height="670" alt="image" src="https://github.com/user-attachments/assets/44f188da-cde6-4c00-a788-3b1218cd2810" />
-

Dashboard - <img width="1280" height="491" alt="image" src="https://github.com/user-attachments/assets/b13b4220-0d2b-48c0-b0c6-e3436a6cec6c" />
-

Overview tab - <img width="1280" height="635" alt="image" src="https://github.com/user-attachments/assets/6126c543-0ef3-4fad-9713-072a6354ad0f" />
-

Notes tab - <img width="1280" height="661" alt="image" src="https://github.com/user-attachments/assets/8b9076db-5c47-44f2-8f30-89cf72537744" />
-

Important timestamps (in both overview and notes tab) - <img width="1280" height="652" alt="image" src="https://github.com/user-attachments/assets/2852d9c0-0bfd-4547-85ab-eb0448e48cd4" />
-

Ai Agent - <img width="1280" height="664" alt="image" src="https://github.com/user-attachments/assets/74b0a1d9-270c-4bba-a127-9defca616ccf" />
-
