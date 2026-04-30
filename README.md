# DocFlow — Async Document Processing Workflow System

A production-style full-stack application for uploading documents, processing them asynchronously, tracking progress in real-time, reviewing extracted output, and exporting finalized results.

---

## Demo Video

> Record a 3–5 minute walkthrough showing: upload → processing progress → review/edit → finalize → export.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (Next.js)                        │
│  Upload Page │ Dashboard │ Document Detail (SSE progress)       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼──────────────────────────────────────┐
│                     FastAPI Backend                             │
│  /api/documents  │  /api/progress/:id/stream (SSE)             │
│  Service Layer   │  Schemas / DTOs                             │
└──────┬───────────────────────────────────────┬─────────────────┘
       │ SQLAlchemy (async)                    │ Redis Pub/Sub subscribe
       │                                       │
┌──────▼──────────┐              ┌─────────────▼──────────────────┐
│   PostgreSQL    │              │            Redis               │
│  documents      │              │  Broker  (DB 1)                │
│  processing_logs│              │  Results (DB 2)                │
└─────────────────┘              │  Pub/Sub (DB 0) + status hash  │
                                 └─────────────┬──────────────────┘
                                               │ Celery broker
                                 ┌─────────────▼──────────────────┐
                                 │        Celery Worker           │
                                 │  process_document task         │
                                 │  Stages: parse → extract →     │
                                 │  store → complete              │
                                 │  Publishes progress via        │
                                 │  Redis Pub/Sub at each stage   │
                                 └────────────────────────────────┘
```

### Key Design Decisions

| Concern | Choice | Reason |
|---|---|---|
| Async API | FastAPI + asyncpg | Non-blocking I/O for upload/list/SSE |
| Background jobs | Celery + Redis broker | Decoupled from request cycle |
| Progress delivery | Redis Pub/Sub → SSE | Real-time push without WebSocket complexity |
| Polling fallback | Redis hash per document | Clients can poll if SSE drops |
| DB sessions | Separate async (FastAPI) + sync (Celery) | Celery workers are synchronous |
| File storage | Local disk (abstracted) | Easily swappable to S3 |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | Python 3.11, FastAPI, SQLAlchemy 2 |
| Database | PostgreSQL 15 |
| Queue / Broker | Celery 5, Redis 7 |
| Progress | Redis Pub/Sub → Server-Sent Events |
| Containerization | Docker Compose |

---

## Features

- **Multi-file upload** with drag-and-drop, validation, and 50 MB limit
- **Async processing** via Celery workers (never in the request cycle)
- **Multi-stage pipeline**: queued → parsing → extraction → storing → completed
- **Live progress** via Server-Sent Events (SSE) backed by Redis Pub/Sub
- **Dashboard** with search, filter by status, sorting, and pagination
- **Document detail** with processing timeline and extracted data view
- **Edit & review** extracted JSON data before finalizing
- **Finalize** to lock the reviewed result
- **Export** finalized documents as JSON or CSV
- **Retry** failed jobs with exponential back-off (up to 3 retries)
- **Delete** documents (removes file from disk)

---

## Project Structure

```
docflow/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── documents.py     # Upload, list, detail, review, finalize, retry, export
│   │   │   └── progress.py      # SSE stream + polling endpoint
│   │   ├── services/
│   │   │   └── document_service.py  # Business logic
│   │   ├── worker/
│   │   │   ├── celery_app.py    # Celery configuration
│   │   │   └── tasks.py         # process_document task (multi-stage)
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # Async + sync SQLAlchemy engines
│   │   ├── models.py            # Document, ProcessingLog ORM models
│   │   ├── redis_client.py      # Pub/Sub publish + status cache
│   │   ├── schemas.py           # Pydantic DTOs
│   │   └── main.py              # FastAPI app, CORS, lifespan
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # Dashboard
│   │   ├── upload/page.tsx      # Upload screen
│   │   └── documents/[id]/page.tsx  # Detail / review / finalize
│   ├── components/
│   │   ├── Navbar.tsx
│   │   ├── StatusBadge.tsx
│   │   ├── ProgressBar.tsx
│   │   └── LiveProgress.tsx     # SSE consumer
│   ├── lib/api.ts               # Axios API client + types
│   └── ...config files
├── sample_files/                # Test documents + sample exports
├── docker-compose.yml
└── README.md
```

---

## Setup & Run

### Option 1 — Docker Compose (recommended)

**Prerequisites:** Docker Desktop

```bash
# Clone and start everything
git clone <repo-url>
cd docflow
docker compose up --build
```

Services start on:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### Option 2 — Local Development

**Prerequisites:** Python 3.11+, Node.js 20+, PostgreSQL 15, Redis 7

#### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env .env.local               # edit DB/Redis URLs if needed

# Start FastAPI
uvicorn app.main:app --reload --port 8000

# In a separate terminal — start Celery worker
celery -A app.worker.celery_app worker --loglevel=info --concurrency=4
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/documents/upload` | Upload one or more files |
| GET | `/api/documents` | List documents (search, filter, sort, paginate) |
| GET | `/api/documents/{id}` | Get document detail with processing logs |
| PATCH | `/api/documents/{id}/review` | Update reviewed data |
| POST | `/api/documents/{id}/finalize` | Finalize document |
| POST | `/api/documents/{id}/retry` | Retry failed job |
| DELETE | `/api/documents/{id}` | Delete document |
| GET | `/api/documents/{id}/export/json` | Export as JSON |
| GET | `/api/documents/{id}/export/csv` | Export as CSV |
| GET | `/api/progress/{id}/stream` | SSE progress stream |
| GET | `/api/progress/{id}/status` | Polling status (Redis cache) |

Full interactive docs at http://localhost:8000/docs

---

## Processing Pipeline

Each document goes through these stages (published via Redis Pub/Sub):

```
job_queued (0%)
    ↓
job_started (5%)
    ↓
document_parsing_started (20%)
    ↓
document_parsing_completed (45%)
    ↓
field_extraction_started (60%)
    ↓
field_extraction_completed (80%)
    ↓
final_result_stored (90%)
    ↓
job_completed (100%)  ──or──  job_failed (0%)
```

Supported file types: PDF, DOCX, TXT, MD, CSV, JSON, XML, HTML

---

## Assumptions

1. File storage is local disk — in production this would be S3 or similar
2. Text extraction is best-effort; binary files get a placeholder
3. "Structured extraction" is keyword/metadata based — no ML/OCR required per spec
4. A single Celery queue is sufficient; priority queues can be added
5. Authentication is out of scope for this assignment (bonus item)

---

## Tradeoffs

| Decision | Tradeoff |
|---|---|
| SSE over WebSockets | Simpler server-side, unidirectional — sufficient for progress |
| Sync Celery workers | Simpler than async Celery; slight overhead for I/O-heavy tasks |
| Auto-create tables on startup | Convenient for dev; production should use Alembic migrations |
| Redis hash for status cache | Fast polling fallback but adds slight Redis memory usage |
| Local file storage | Simple; not horizontally scalable without shared volume or object storage |

---

## Limitations

- No authentication / authorization
- File storage is not distributed (single-node)
- No cancellation support (bonus item)
- PDF text extraction quality depends on PDF structure (no OCR)
- No rate limiting on upload endpoint

---

## Bonus Features Implemented

- [x] Docker Compose setup
- [x] Idempotent retry handling (retry_count tracked, Celery exponential back-off)
- [x] File storage abstraction (upload_dir configurable)
- [x] Polling fallback alongside SSE

---

## AI Tools Used

GitHub Copilot / Claude was used to assist with boilerplate generation and code review. All architecture decisions, design choices, and implementation logic were authored by the developer.

---

## Sample Files

See `sample_files/` directory:
- `sample_report.txt` — plain text financial report
- `sample_data.json` — JSON configuration file
- `sample_notes.md` — Markdown meeting notes
- `sample_export_output.json` — example JSON export
- `sample_export_output.csv` — example CSV export
