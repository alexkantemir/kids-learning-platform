from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.child import Child
from app.models.quiz import Quiz
from app.models.attempt import QuizAttempt
from app.models.lesson import Lesson
from app.api.deps import get_current_user
from app.services.gamification import update_streak, check_and_award_achievements, update_subject_progress

router = APIRouter()


class QuizSubmit(BaseModel):
    answers: list[int]
    time_spent_seconds: int | None = None


@router.post("/{quiz_id}/attempt")
async def submit_quiz(
    quiz_id: int,
    data: QuizSubmit,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Quiz)
        .where(Quiz.id == quiz_id)
        .options(selectinload(Quiz.questions), selectinload(Quiz.lesson))
    )
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    if user.role != UserRole.child:
        raise HTTPException(status_code=403, detail="Only child accounts can submit quizzes")

    child_result = await db.execute(select(Child).where(Child.user_id == user.id))
    child = child_result.scalar_one_or_none()
    if not child:
        raise HTTPException(status_code=403, detail="No child profile")

    # Verify this quiz belongs to this child
    lesson_result = await db.execute(
        select(Lesson).where(Lesson.id == quiz.lesson_id, Lesson.child_id == child.id)
    )
    if not lesson_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied")

    # Calculate score
    correct = 0
    for i, question in enumerate(quiz.questions):
        if i < len(data.answers) and data.answers[i] == question.correct_index:
            correct += 1

    score = correct / len(quiz.questions) if quiz.questions else 0.0
    xp_earned = int(score * 20)

    attempt = QuizAttempt(
        quiz_id=quiz_id,
        child_id=child.id,
        score=score,
        answers=data.answers,
        time_spent_seconds=data.time_spent_seconds,
        xp_earned=xp_earned,
    )
    db.add(attempt)

    # Update child XP and streak
    child.xp += xp_earned
    await update_streak(child)

    # Update subject progress
    lesson = await db.get(Lesson, quiz.lesson_id)
    if lesson:
        from app.models.topic import Topic
        topic = await db.get(Topic, lesson.topic_id)
        if topic:
            await update_subject_progress(child.id, topic.subject_id, xp_earned, db)

    new_achievements = await check_and_award_achievements(child, db)
    await db.flush()

    # Get correct answers for display
    correct_answers = [q.correct_index for q in quiz.questions]
    explanations = [q.explanation for q in quiz.questions]

    return {
        "score": round(score, 2),
        "correct": correct,
        "total": len(quiz.questions),
        "xp_earned": xp_earned,
        "attempt_id": attempt.id,
        "correct_answers": correct_answers,
        "explanations": explanations,
        "new_achievements": new_achievements,
    }


@router.get("/{quiz_id}/attempts")
async def get_quiz_attempts(
    quiz_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role != UserRole.child:
        raise HTTPException(status_code=403, detail="Child account required")
    child_result = await db.execute(select(Child).where(Child.user_id == user.id))
    child = child_result.scalar_one_or_none()
    if not child:
        raise HTTPException(status_code=403, detail="No child profile")

    result = await db.execute(
        select(QuizAttempt)
        .where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.child_id == child.id)
        .order_by(QuizAttempt.created_at.desc())
    )
    attempts = result.scalars().all()
    return [
        {
            "id": a.id,
            "score": a.score,
            "xp_earned": a.xp_earned,
            "created_at": a.created_at,
        }
        for a in attempts
    ]
