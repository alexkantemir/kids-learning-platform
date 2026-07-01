import enum
from datetime import datetime, timezone

from sqlalchemy import String, ForeignKey, DateTime, Text, Integer, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AIRequestStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"
    invalid_response = "invalid_response"


class AIRequest(Base):
    __tablename__ = "ai_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[AIRequestStatus] = mapped_column(SAEnum(AIRequestStatus), default=AIRequestStatus.pending)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    auto_fixed_log: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id"), nullable=True)
    lesson: Mapped["Lesson | None"] = relationship("Lesson", back_populates="ai_requests")
