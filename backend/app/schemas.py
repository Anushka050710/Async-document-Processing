from pydantic import BaseModel, Field
from typing import Optional, Any, List
from datetime import datetime
from uuid import UUID
from app.models import JobStatus


# ── Processing Log ──────────────────────────────────────────────────────────

class ProcessingLogOut(BaseModel):
    id: UUID
    event: str
    message: Optional[str]
    progress: float
    created_at: datetime

    class Config:
        from_attributes = True


# ── Document ─────────────────────────────────────────────────────────────────

class DocumentBase(BaseModel):
    filename: str
    original_filename: str
    file_size: int
    file_type: str
    mime_type: Optional[str] = None


class DocumentOut(DocumentBase):
    id: UUID
    status: JobStatus
    celery_task_id: Optional[str] = None
    retry_count: int
    error_message: Optional[str] = None
    progress: float
    current_stage: Optional[str] = None
    extracted_data: Optional[Any] = None
    reviewed_data: Optional[Any] = None
    is_finalized: bool
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentDetailOut(DocumentOut):
    processing_logs: List[ProcessingLogOut] = []

    class Config:
        from_attributes = True


class DocumentListOut(BaseModel):
    items: List[DocumentOut]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Update / Finalize ─────────────────────────────────────────────────────────

class ReviewedDataUpdate(BaseModel):
    reviewed_data: Any = Field(..., description="Edited extracted data")


class FinalizeRequest(BaseModel):
    reviewed_data: Optional[Any] = None


# ── Progress Event ────────────────────────────────────────────────────────────

class ProgressEvent(BaseModel):
    document_id: str
    event: str
    message: str
    progress: float
    status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Upload Response ───────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    uploaded: List[DocumentOut]
    failed: List[dict] = []
