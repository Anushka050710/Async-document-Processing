import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, JSON,
    ForeignKey, Enum as SAEnum, Boolean
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
from app.database import Base


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    FINALIZED = "finalized"


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_type = Column(String(100), nullable=False)
    mime_type = Column(String(100), nullable=True)
    status = Column(SAEnum(JobStatus), default=JobStatus.QUEUED, nullable=False, index=True)
    celery_task_id = Column(String(255), nullable=True)
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    progress = Column(Float, default=0.0)
    current_stage = Column(String(100), nullable=True)

    # Extracted data
    extracted_data = Column(JSON, nullable=True)
    reviewed_data = Column(JSON, nullable=True)
    is_finalized = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    processing_logs = relationship("ProcessingLog", back_populates="document", cascade="all, delete-orphan")


class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    event = Column(String(100), nullable=False)
    message = Column(Text, nullable=True)
    progress = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    document = relationship("Document", back_populates="processing_logs")
