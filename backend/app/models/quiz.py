from sqlalchemy import String, ForeignKey, Text, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(primary_key=True)

    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), unique=True)
    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="quiz")

    questions: Mapped[list["QuizQuestion"]] = relationship(
        "QuizQuestion", back_populates="quiz", order_by="QuizQuestion.sort_order"
    )
    attempts: Mapped[list["QuizAttempt"]] = relationship("QuizAttempt", back_populates="quiz")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    question: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON)
    correct_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)

    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"))
    quiz: Mapped["Quiz"] = relationship("Quiz", back_populates="questions")
