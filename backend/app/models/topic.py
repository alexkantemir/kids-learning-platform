from datetime import datetime, timezone

from sqlalchemy import String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(default=1)  # 1-3
    is_catalog: Mapped[bool] = mapped_column(Boolean, default=True)  # False = user-created
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)  # For custom topics needing approval
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    subject: Mapped["Subject"] = relationship("Subject", back_populates="topics")

    lessons: Mapped[list["Lesson"]] = relationship("Lesson", back_populates="topic")
    plan_items: Mapped[list["PlanItem"]] = relationship("PlanItem", back_populates="topic")
