import enum
from datetime import datetime, timezone

from sqlalchemy import String, ForeignKey, DateTime, Text, Integer, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LessonStatus(str, enum.Enum):
    generating = "generating"
    ready = "ready"
    failed = "failed"
    needs_review = "needs_review"


class StepType(str, enum.Enum):
    explain = "explain"
    game = "game"


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    age_band: Mapped[str] = mapped_column(String(16))
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    story_intro: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[LessonStatus] = mapped_column(SAEnum(LessonStatus), default=LessonStatus.generating)
    raw_ai_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    xp_reward: Mapped[int] = mapped_column(Integer, default=20)
    badge_candidate: Mapped[str | None] = mapped_column(String(128), nullable=True)
    validation_errors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    generation_attempts: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"))
    child: Mapped["Child"] = relationship("Child", back_populates="lessons")

    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    topic: Mapped["Topic"] = relationship("Topic", back_populates="lessons")

    steps: Mapped[list["LessonStep"]] = relationship("LessonStep", back_populates="lesson", order_by="LessonStep.sort_order")
    quiz: Mapped["Quiz | None"] = relationship("Quiz", back_populates="lesson", uselist=False)
    ai_requests: Mapped[list["AIRequest"]] = relationship("AIRequest", back_populates="lesson")


class LessonStep(Base):
    __tablename__ = "lesson_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    step_type: Mapped[StepType] = mapped_column(SAEnum(StepType))
    step_subtype: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    task: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    correct_option_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback_correct: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_wrong: Mapped[str | None] = mapped_column(Text, nullable=True)
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="steps")
