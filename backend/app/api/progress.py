import asyncio
import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db
from app.redis_client import redis_client, get_channel_name, get_latest_status
from app.services.document_service import get_document

router = APIRouter(prefix="/api/progress", tags=["progress"])


@router.get("/{document_id}/stream")
async def stream_progress(
    document_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Server-Sent Events endpoint.
    Subscribes to Redis Pub/Sub channel for the document and streams
    progress events to the client until the job completes or fails.
    """
    # Validate document exists
    await get_document(document_id, db)

    async def event_generator():
        # Send the latest cached status immediately so the client isn't blank
        latest = get_latest_status(document_id)
        if latest:
            yield f"data: {json.dumps(latest)}\n\n"

        # Subscribe to the Redis channel in a thread pool (redis-py is sync)
        loop = asyncio.get_event_loop()
        pubsub = redis_client.pubsub()
        channel = get_channel_name(document_id)

        await loop.run_in_executor(None, pubsub.subscribe, channel)

        try:
            terminal_events = {"job_completed", "job_failed"}
            while True:
                message = await loop.run_in_executor(None, pubsub.get_message, True, 0.1)
                if message and message["type"] == "message":
                    data = message["data"]
                    yield f"data: {data}\n\n"

                    # Stop streaming once terminal event received
                    try:
                        parsed = json.loads(data)
                        if parsed.get("event") in terminal_events:
                            break
                    except Exception:
                        pass
                else:
                    # Heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
                    await asyncio.sleep(0.5)
        finally:
            await loop.run_in_executor(None, pubsub.unsubscribe, channel)
            await loop.run_in_executor(None, pubsub.close)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/{document_id}/status")
async def get_progress_status(
    document_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Polling fallback: returns the latest cached progress from Redis."""
    await get_document(document_id, db)
    status = get_latest_status(document_id)
    if not status:
        return {"document_id": document_id, "message": "No progress data yet"}
    return status
