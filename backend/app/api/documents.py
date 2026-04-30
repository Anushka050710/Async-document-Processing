import math
import json
import csv
import io
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, Query, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.schemas import (
    DocumentOut, DocumentDetailOut, DocumentListOut,
    ReviewedDataUpdate, FinalizeRequest, UploadResponse,
)
from app.services import document_service as svc
from app.worker.tasks import process_document
from app.models import JobStatus

router = APIRouter(prefix="/api/documents", tags=["documents"])


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, status_code=201)
async def upload_documents(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_async_db),
):
    """Upload one or more documents and enqueue processing jobs."""
    uploaded = []
    failed = []

    for file in files:
        try:
            doc = await svc.save_upload(file, db)
            uploaded.append(doc)
        except HTTPException as exc:
            failed.append({"filename": file.filename, "error": exc.detail})
        except Exception as exc:
            failed.append({"filename": file.filename, "error": str(exc)})

    await db.commit()

    # Dispatch Celery tasks AFTER commit so IDs are persisted
    for doc in uploaded:
        task = process_document.delay(str(doc.id))
        doc.celery_task_id = task.id
        await db.commit()

    return UploadResponse(
        uploaded=[DocumentOut.model_validate(d) for d in uploaded],
        failed=failed,
    )


# ── List / Search ─────────────────────────────────────────────────────────────

@router.get("", response_model=DocumentListOut)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort_by: str = Query("created_at", regex="^(created_at|updated_at|original_filename|status|file_size)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_async_db),
):
    items, total = await svc.list_documents(db, page, page_size, search, status, sort_by, sort_order)
    return DocumentListOut(
        items=[DocumentOut.model_validate(d) for d in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{document_id}", response_model=DocumentDetailOut)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    doc = await svc.get_document_with_logs(document_id, db)
    return DocumentDetailOut.model_validate(doc)


# ── Update reviewed data ──────────────────────────────────────────────────────

@router.patch("/{document_id}/review", response_model=DocumentOut)
async def update_review(
    document_id: str,
    body: ReviewedDataUpdate,
    db: AsyncSession = Depends(get_async_db),
):
    doc = await svc.update_reviewed_data(document_id, body.reviewed_data, db)
    await db.commit()
    return DocumentOut.model_validate(doc)


# ── Finalize ──────────────────────────────────────────────────────────────────

@router.post("/{document_id}/finalize", response_model=DocumentOut)
async def finalize_document(
    document_id: str,
    body: FinalizeRequest,
    db: AsyncSession = Depends(get_async_db),
):
    doc = await svc.finalize_document(document_id, body.reviewed_data, db)
    await db.commit()
    return DocumentOut.model_validate(doc)


# ── Retry ─────────────────────────────────────────────────────────────────────

@router.post("/{document_id}/retry", response_model=DocumentOut)
async def retry_document(
    document_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    doc = await svc.retry_document(document_id, db)
    await db.commit()
    task = process_document.delay(str(doc.id))
    doc.celery_task_id = task.id
    await db.commit()
    return DocumentOut.model_validate(doc)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    await svc.delete_document(document_id, db)
    await db.commit()


# ── Export ────────────────────────────────────────────────────────────────────

@router.get("/{document_id}/export/json")
async def export_json(
    document_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    doc = await svc.get_document(document_id, db)
    if not doc.is_finalized:
        raise HTTPException(status_code=400, detail="Document must be finalized before export")

    payload = {
        "id": str(doc.id),
        "original_filename": doc.original_filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "status": doc.status,
        "created_at": doc.created_at.isoformat(),
        "completed_at": doc.completed_at.isoformat() if doc.completed_at else None,
        "extracted_data": doc.extracted_data,
        "reviewed_data": doc.reviewed_data,
    }
    content = json.dumps(payload, indent=2, default=str)
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{doc.original_filename}.json"'},
    )


@router.get("/{document_id}/export/csv")
async def export_csv(
    document_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    doc = await svc.get_document(document_id, db)
    if not doc.is_finalized:
        raise HTTPException(status_code=400, detail="Document must be finalized before export")

    data = doc.reviewed_data or doc.extracted_data or {}
    output = io.StringIO()
    writer = csv.writer(output)

    # Flatten top-level keys
    writer.writerow(["field", "value"])
    for key, value in data.items():
        if isinstance(value, list):
            writer.writerow([key, ", ".join(str(v) for v in value)])
        else:
            writer.writerow([key, str(value) if value is not None else ""])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{doc.original_filename}.csv"'},
    )
