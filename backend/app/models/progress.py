from datetime import datetime, timezone

from sqlalchemy import ForeignKey, DateTime, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Progress(Base):
    __tablename__ = "progress"
    __table_args__ = (UniqueConstraint("child_id", "subject_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lessons_completed: Mapped[int] = mapped_column(Integer, default=0)
    quizzes_passed: Mapped[int] = mapped_column(Integer, default=0)
    total_xp: Mapped[int] = mapped_column(Integer, default=0)
    last_activity: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"))
    child: Mapped["Child"] = relationship("Child", back_populates="progress")

    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    subject: Mapped["Subject"] = relationship("Subject", back_populates="progress")
