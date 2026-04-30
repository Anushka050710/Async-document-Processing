import redis
import json
from datetime import datetime
from app.config import get_settings

settings = get_settings()

# Synchronous Redis client (used by Celery workers and SSE)
redis_client = redis.from_url(settings.redis_url, decode_responses=True)


def get_channel_name(document_id: str) -> str:
    return f"docflow:progress:{document_id}"


def publish_progress(
    document_id: str,
    event: str,
    message: str,
    progress: float,
    status: str,
) -> None:
    """Publish a progress event to Redis Pub/Sub."""
    payload = {
        "document_id": document_id,
        "event": event,
        "message": message,
        "progress": progress,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
    }
    channel = get_channel_name(document_id)
    redis_client.publish(channel, json.dumps(payload))

    # Also store latest status — use hmset for Redis 3.x compatibility
    key = f"docflow:status:{document_id}"
    status_data = {
        "event": event,
        "message": message,
        "progress": str(progress),
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
    }
    try:
        # Redis 4+ supports hset with mapping
        redis_client.hset(key, mapping=status_data)
    except Exception:
        # Redis 3.x fallback — set each field individually
        for k, v in status_data.items():
            redis_client.hset(key, k, v)
    # Expire after 24 hours
    redis_client.expire(key, 86400)


def get_latest_status(document_id: str) -> dict | None:
    """Get the latest cached status for a document."""
    data = redis_client.hgetall(f"docflow:status:{document_id}")
    if not data:
        return None
    return {
        "document_id": document_id,
        "event": data.get("event", ""),
        "message": data.get("message", ""),
        "progress": float(data.get("progress", 0)),
        "status": data.get("status", ""),
        "timestamp": data.get("timestamp", ""),
    }
