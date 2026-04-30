import time
import os
import uuid
from datetime import datetime
from celery import Task
from celery.utils.log import get_task_logger

from app.worker.celery_app import celery_app
from app.redis_client import publish_progress
from app.config import get_settings
from app.models import JobStatus

logger = get_task_logger(__name__)
settings = get_settings()


class DocumentProcessingTask(Task):
    """Base task with DB session management."""
    abstract = True
    _db = None

    @property
    def db(self):
        if self._db is None:
            from app.database import SyncSessionLocal
            self._db = SyncSessionLocal()
        return self._db

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        if self._db is not None:
            self._db.close()
            self._db = None


def _emit(document_id: str, event: str, message: str, progress: float, status: str):
    """Publish progress and log to DB."""
    publish_progress(document_id, event, message, progress, status)
    logger.info(f"[{document_id}] {event}: {message} ({progress:.0f}%)")


def _log_to_db(db, document_id: str, event: str, message: str, progress: float):
    """Persist a processing log entry."""
    from app.models import ProcessingLog
    log = ProcessingLog(
        document_id=uuid.UUID(document_id),
        event=event,
        message=message,
        progress=progress,
    )
    db.add(log)
    db.commit()


def _update_document(db, document_id: str, **kwargs):
    """Update document fields."""
    from app.models import Document
    doc = db.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
    if doc:
        for key, value in kwargs.items():
            setattr(doc, key, value)
        doc.updated_at = datetime.utcnow()
        db.commit()
    return doc


# ── Processor helpers ─────────────────────────────────────────────────────────

def _parse_document(file_path: str, file_type: str, original_filename: str) -> dict:
    """Extract raw text / metadata from the file."""
    text_content = ""
    page_count = None

    ext = file_type.lower().lstrip(".")

    try:
        if ext == "pdf":
            import PyPDF2
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                page_count = len(reader.pages)
                for page in reader.pages:
                    text_content += page.extract_text() or ""
        elif ext in ("docx",):
            from docx import Document as DocxDocument
            doc = DocxDocument(file_path)
            text_content = "\n".join(p.text for p in doc.paragraphs)
        elif ext in ("txt", "md", "csv", "json", "xml", "html"):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text_content = f.read()
        else:
            # Binary / unknown — just note the filename
            text_content = f"[Binary file: {original_filename}]"
    except Exception as exc:
        text_content = f"[Parse error: {exc}]"

    return {
        "raw_text": text_content[:5000],  # cap at 5 000 chars
        "page_count": page_count,
        "char_count": len(text_content),
    }


def _extract_fields(parsed: dict, original_filename: str, file_size: int, file_type: str) -> dict:
    """Generate structured fields from parsed content."""
    raw_text = parsed.get("raw_text", "")
    words = [w for w in raw_text.split() if len(w) > 3]

    # Simple keyword extraction: top 10 most-frequent long words
    from collections import Counter
    freq = Counter(words)
    keywords = [w for w, _ in freq.most_common(10)]

    # Derive a title from the filename (strip extension, replace separators)
    base = os.path.splitext(original_filename)[0]
    title = base.replace("_", " ").replace("-", " ").title()

    # Naive category from extension
    category_map = {
        "pdf": "PDF Document",
        "docx": "Word Document",
        "txt": "Plain Text",
        "csv": "Spreadsheet / Data",
        "json": "JSON Data",
        "md": "Markdown",
        "xml": "XML Data",
        "html": "Web Page",
    }
    category = category_map.get(file_type.lower().lstrip("."), "Unknown")

    # Summary: first 200 chars of text or a placeholder
    summary = (raw_text[:200].strip() + "…") if len(raw_text) > 200 else (raw_text.strip() or "No text content found.")

    return {
        "title": title,
        "category": category,
        "summary": summary,
        "keywords": keywords,
        "page_count": parsed.get("page_count"),
        "char_count": parsed.get("char_count", 0),
        "file_size_bytes": file_size,
        "file_type": file_type,
        "original_filename": original_filename,
        "processed_at": datetime.utcnow().isoformat(),
    }


# ── Main Celery task ──────────────────────────────────────────────────────────

@celery_app.task(
    bind=True,
    base=DocumentProcessingTask,
    name="app.worker.tasks.process_document",
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def process_document(self, document_id: str):
    """
    Multi-stage async document processing task.
    Publishes progress events via Redis Pub/Sub at each stage.
    """
    db = self.db

    def emit(event, message, progress, status=JobStatus.PROCESSING):
        _emit(document_id, event, message, progress, status)
        _log_to_db(db, document_id, event, message, progress)
        _update_document(db, document_id, progress=progress, current_stage=event, status=status)

    try:
        # ── Stage 0: job_started ──────────────────────────────────────────
        emit("job_started", "Job picked up by worker", 5, JobStatus.PROCESSING)
        time.sleep(0.5)

        # Fetch document record
        from app.models import Document
        doc = db.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found in database")

        file_path = doc.file_path
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # ── Stage 1: document_parsing_started ────────────────────────────
        emit("document_parsing_started", "Parsing document content…", 20)
        time.sleep(1)

        parsed = _parse_document(file_path, doc.file_type, doc.original_filename)

        # ── Stage 2: document_parsing_completed ──────────────────────────
        emit("document_parsing_completed", f"Parsed {parsed['char_count']} characters", 45)
        time.sleep(0.5)

        # ── Stage 3: field_extraction_started ────────────────────────────
        emit("field_extraction_started", "Extracting structured fields…", 60)
        time.sleep(1)

        extracted = _extract_fields(parsed, doc.original_filename, doc.file_size, doc.file_type)

        # ── Stage 4: field_extraction_completed ──────────────────────────
        emit("field_extraction_completed", f"Extracted {len(extracted)} fields", 80)
        time.sleep(0.5)

        # ── Stage 5: final_result_stored ─────────────────────────────────
        emit("final_result_stored", "Storing results in database…", 90)
        _update_document(
            db,
            document_id,
            extracted_data=extracted,
            reviewed_data=extracted,  # pre-populate reviewed with extracted
        )
        time.sleep(0.3)

        # ── Stage 6: job_completed ────────────────────────────────────────
        _update_document(
            db,
            document_id,
            status=JobStatus.COMPLETED,
            progress=100.0,
            current_stage="job_completed",
            completed_at=datetime.utcnow(),
        )
        emit("job_completed", "Document processed successfully", 100, JobStatus.COMPLETED)

        return {"status": "completed", "document_id": document_id}

    except Exception as exc:
        logger.exception(f"Processing failed for document {document_id}: {exc}")

        # Update retry count
        from app.models import Document as _Document
        doc_obj = db.query(_Document).filter(_Document.id == uuid.UUID(document_id)).first()
        retry_count = (doc_obj.retry_count if doc_obj else 0) + 1

        _update_document(
            db,
            document_id,
            status=JobStatus.FAILED,
            error_message=str(exc),
            current_stage="job_failed",
            retry_count=retry_count,
        )
        _emit(document_id, "job_failed", f"Processing failed: {exc}", 0, JobStatus.FAILED)
        _log_to_db(db, document_id, "job_failed", str(exc), 0)

        # Celery retry with exponential back-off
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=10 * (2 ** self.request.retries))

        raise
