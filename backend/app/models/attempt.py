from datetime import datetime, timezone

from sqlalchemy import ForeignKey, DateTime, Integer, JSON, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0 - 1.0
    answers: Mapped[list] = mapped_column(JSON, default=list)  # list of chosen indices
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    xp_earned: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"))
    quiz: Mapped["Quiz"] = relationship("Quiz", back_populates="attempts")

    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"))
    child: Mapped["Child"] = relationship("Child")
