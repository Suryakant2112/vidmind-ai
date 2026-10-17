# VidMind AI — AI Video Summarizer, Lecture Notes & Q&A

An AI-powered learning assistant that transforms YouTube lectures into structured summaries, detailed study notes, and interactive Q&A — all grounded in the video's transcript using **Retrieval-Augmented Generation (RAG)**.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)
![LangChain](https://img.shields.io/badge/LangChain-0.3+-orange)
![Qdrant](https://img.shields.io/badge/Qdrant-1.12+-purple)

---

## 🎯 Features

- **🎬 YouTube Transcript Extraction** — Automatically fetches transcripts with timestamp preservation
- **📋 AI Video Summary** — Structured overview with main topics, key points, and takeaways
- **📝 AI Lecture Notes** — Detailed, study-optimized notes with definitions, formulas, and examples
- **💬 RAG-Based Q&A** — Ask questions grounded in the video's transcript
- **⏱ Timestamp Sources** — Clickable timestamps linking back to the exact moment in the video
- **🔄 Conversational Follow-ups** — Multi-turn Q&A with context awareness
- **🧠 Local Embeddings** — FastEmbed (ONNX) on CPU, light enough for free hosting
- **💾 Persistent Vector Storage** — Qdrant (Cloud or local), also caches summaries & notes
- **🔁 LLM Fallback Chain** — Groq → second Groq model → Gemini, to stretch free limits
- **📋 Paste Transcript** — Works even when YouTube blocks the server from fetching captions
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
          │ FastEmbed Embeddings │  ← all-MiniLM-L6-v2 (ONNX, local CPU)
          │     Embeddings       │
          └──────────┬──────────┘
                     │
                     ↓
          ┌─────────────────────┐
          │       Qdrant         │  ← Qdrant Cloud (free) or local
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
          │ Groq → Gemini chain  │  ← free tiers, automatic fallback
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
| Embeddings | FastEmbed (`all-MiniLM-L6-v2`, ONNX) | Free (CPU) |
| RAG retrieval | Qdrant similarity search | Free |
| Web server | FastAPI + Uvicorn | Free |

### What Uses External API (Free Tier)

| Component | Technology | Cost |
|---|---|---|
| LLM inference | Groq (`qwen/qwen3.8-27b`, then `openai/gpt-oss-120b`) → Gemini (`gemini-3.5-flash-lite`) | Free tiers (rate-limited) |
| Vector database | Qdrant Cloud (or embedded local Qdrant) | Free tier |

---

## 🛠 Tech Stack

| Layer | Technology | Role |
|---|---|---|
| **Backend** | FastAPI | REST API, async request handling |
| **LLM** | Groq + Gemini (via `langchain-openai`) | Text generation with provider fallback |
| **Embeddings** | FastEmbed (ONNX Runtime) | Local vector embeddings (CPU) |
| **Vector DB** | Qdrant | Semantic search + cached summaries/notes |
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
   Question Embedding          ← FastEmbed (local)
         │
         ↓
   Qdrant Similarity Search    ← Find top-K most relevant transcript chunks
         │
         ↓
   Context Construction         ← Combine retrieved chunks with timestamps
         │
         ↓
   LLM Prompt                  ← System prompt enforces grounding policy
         │
         ↓
   Groq / Gemini               ← Generate answer using ONLY retrieved context
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
Semantic Chunks (Qdrant)
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
- Optional: a free Gemini API key ([aistudio.google.com](https://aistudio.google.com)) as a fallback

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
# LLM providers, tried in order (any without a key is skipped)
LLM_API_KEY=your_groq_api_key_here      # https://console.groq.com
LLM_MODEL=qwen/qwen3.8-27b
LLM_FALLBACK_MODEL=openai/gpt-oss-120b  # separate Groq rate-limit bucket
GEMINI_API_KEY=                         # https://aistudio.google.com (optional)
GEMINI_MODEL=gemini-3.5-flash-lite

# Local embedding model (downloaded automatically, ~90MB)
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Vector database — leave QDRANT_URL empty to use a local database in ./qdrant_data
QDRANT_URL=
QDRANT_API_KEY=

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

**First run**: The FastEmbed model (~90MB) is downloaded automatically into `.model_cache/`. This only happens once.

Videos processed before this version (stored in ChromaDB) need to be processed again.

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

### Example: Process with a Pasted Transcript

```bash
curl -X POST http://localhost:8000/api/video/process   -H "Content-Type: application/json"   -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID", "transcript": "0:00
Welcome...
0:05
Today..."}'
```

If fetching the transcript fails, the API returns `422` with `{"detail": {"code": "transcript_unavailable", ...}}` and the web page opens the paste box.

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

### Deploy for Free on Render

The app runs on Render's free web service (512 MB RAM) with Qdrant Cloud's free cluster for storage.

1. **Qdrant Cloud** — create a free cluster at [cloud.qdrant.io](https://cloud.qdrant.io) and copy its URL and API key.
2. **API keys** — get a Groq key ([console.groq.com](https://console.groq.com)) and, optionally, a Gemini key ([aistudio.google.com](https://aistudio.google.com)).
3. **Render** — push this repo to GitHub, then in Render choose **New → Blueprint** and select the repo. `render.yaml` sets everything up; enter `LLM_API_KEY`, `GEMINI_API_KEY`, `QDRANT_URL` and `QDRANT_API_KEY` when asked.
4. Open the `onrender.com` URL Render gives you.

**What to expect on the free tier:**
- The service sleeps after ~15 minutes idle; the first visit afterwards takes about a minute.
- **YouTube often blocks transcript requests from cloud servers.** When that happens, the page opens a paste box — copy the transcript from YouTube (description → *Show transcript*) and paste it in.
- Processed videos, summaries and notes live in Qdrant Cloud, so they survive restarts.
- Free-tier limits change often; check each provider's dashboard for your current limits.

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
- Groq free tier has rate limits (requests per minute/day) per model — the app falls back to a second Groq model, then Gemini
- Gemini's free tier may use your prompts to improve Google's products
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
- YouTube may block transcript fetching from cloud servers — use the paste box
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
│   │   ├── embedding_service.py   # FastEmbed embeddings
│   │   ├── vector_store.py        # Qdrant: chunks + video records
│   │   ├── llm_service.py         # Groq → Gemini fallback chain
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
├── qdrant_data/                   # Local vector storage (when QDRANT_URL is empty)
├── .env.example                   # Environment variable template
├── .gitignore
├── requirements.txt
├── Dockerfile
├── render.yaml                    # Render deployment blueprint
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
