import os
import uuid
import shutil
import mimetypes
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, desc, asc
from fastapi import UploadFile, HTTPException

from app.models import Document, ProcessingLog, JobStatus
from app.config import get_settings
from app.redis_client import publish_progress

settings = get_settings()


# ── Upload ────────────────────────────────────────────────────────────────────

async def save_upload(file: UploadFile, db: AsyncSession) -> Document:
    """Persist an uploaded file and create a Document record."""
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Unique filename to avoid collisions
    ext = os.path.splitext(file.filename or "file")[1].lower() or ".bin"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(settings.upload_dir, unique_name)

    # Stream to disk
    size = 0
    with open(file_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):  # 1 MB chunks
            if size + len(chunk) > settings.max_upload_size:
                os.remove(file_path)
                raise HTTPException(status_code=413, detail=f"File '{file.filename}' exceeds 50 MB limit")
            out.write(chunk)
            size += len(chunk)

    mime_type = file.content_type or mimetypes.guess_type(file.filename or "")[0]
    file_type = ext.lstrip(".")

    doc = Document(
        filename=unique_name,
        original_filename=file.filename or unique_name,
        file_path=file_path,
        file_size=size,
        file_type=file_type,
        mime_type=mime_type,
        status=JobStatus.QUEUED,
    )
    db.add(doc)
    await db.flush()  # get the ID before commit

    # Publish initial queued event
    publish_progress(
        str(doc.id), "job_queued",
        "Document uploaded and queued for processing",
        0.0, JobStatus.QUEUED,
    )

    return doc


# ── List / Search ─────────────────────────────────────────────────────────────

async def list_documents(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    query = select(Document)

    if search:
        query = query.where(
            or_(
                Document.original_filename.ilike(f"%{search}%"),
                Document.file_type.ilike(f"%{search}%"),
            )
        )

    if status:
        try:
            status_enum = JobStatus(status)
            query = query.where(Document.status == status_enum)
        except ValueError:
            pass

    # Sorting
    sort_col = getattr(Document, sort_by, Document.created_at)
    if sort_order == "asc":
        query = query.order_by(asc(sort_col))
    else:
        query = query.order_by(desc(sort_col))

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return items, total


# ── Detail ────────────────────────────────────────────────────────────────────

async def get_document(document_id: str, db: AsyncSession) -> Document:
    result = await db.execute(
        select(Document).where(Document.id == uuid.UUID(document_id))
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


async def get_document_with_logs(document_id: str, db: AsyncSession) -> Document:
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.processing_logs))
        .where(Document.id == uuid.UUID(document_id))
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ── Update / Finalize ─────────────────────────────────────────────────────────

async def update_reviewed_data(document_id: str, reviewed_data: dict, db: AsyncSession) -> Document:
    doc = await get_document(document_id, db)
    if doc.status not in (JobStatus.COMPLETED, JobStatus.FINALIZED):
        raise HTTPException(status_code=400, detail="Document must be completed before reviewing")
    doc.reviewed_data = reviewed_data
    doc.updated_at = datetime.utcnow()
    await db.flush()
    return doc


async def finalize_document(document_id: str, reviewed_data, db: AsyncSession) -> Document:
    doc = await get_document(document_id, db)
    if doc.status not in (JobStatus.COMPLETED, JobStatus.FINALIZED):
        raise HTTPException(status_code=400, detail="Document must be completed before finalizing")
    if reviewed_data is not None:
        doc.reviewed_data = reviewed_data
    doc.is_finalized = True
    doc.status = JobStatus.FINALIZED
    doc.updated_at = datetime.utcnow()
    await db.flush()
    return doc


# ── Retry ─────────────────────────────────────────────────────────────────────

async def retry_document(document_id: str, db: AsyncSession) -> Document:
    doc = await get_document(document_id, db)
    if doc.status != JobStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried")

    doc.status = JobStatus.QUEUED
    doc.error_message = None
    doc.progress = 0.0
    doc.current_stage = None
    doc.updated_at = datetime.utcnow()
    await db.flush()

    publish_progress(str(doc.id), "job_queued", "Job re-queued for retry", 0.0, JobStatus.QUEUED)
    return doc


# ── Delete ────────────────────────────────────────────────────────────────────

async def delete_document(document_id: str, db: AsyncSession) -> None:
    doc = await get_document(document_id, db)
    # Remove file from disk
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    await db.delete(doc)
    await db.flush()
