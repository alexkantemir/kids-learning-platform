from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload
import re

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.child import Child
from app.models.lesson import Lesson
from app.models.attempt import QuizAttempt
from app.models.achievement import ChildAchievement, Achievement
from app.models.progress import Progress
from app.models.subject import Subject
from app.schemas.child import ChildResponse, ChildCreate
from app.api.deps import get_current_parent
from app.core.security import hash_password, verify_password

router = APIRouter()


class PasswordChangeOwn(BaseModel):
    current_password: str
    new_password: str


class PasswordChangeChild(BaseModel):
    new_password: str


@router.get("/dashboard")
async def parent_dashboard(
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    children_result = await db.execute(
        select(Child).where(Child.parent_id == parent.id)
    )
    children = children_result.scalars().all()

    dashboard = []
    for child in children:
        lessons_count = await db.execute(
            select(func.count()).where(Lesson.child_id == child.id, Lesson.status == "ready")
        )
        attempts_count = await db.execute(
            select(func.count()).where(QuizAttempt.child_id == child.id)
        )
        dashboard.append({
            "child": ChildResponse.model_validate(child),
            "total_lessons": lessons_count.scalar_one(),
            "total_quiz_attempts": attempts_count.scalar_one(),
        })

    return {"children": dashboard}


@router.get("/child/{child_id}/detail")
async def child_detail(
    child_id: int,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    child_result = await db.execute(
        select(Child).where(Child.id == child_id, Child.parent_id == parent.id)
    )
    child = child_result.scalar_one_or_none()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")

    # Recent lessons (last 10)
    lessons_result = await db.execute(
        select(Lesson)
        .where(Lesson.child_id == child_id, Lesson.status == "ready")
        .options(selectinload(Lesson.topic))
        .order_by(Lesson.created_at.desc())
        .limit(10)
    )
    lessons = lessons_result.scalars().all()

    # Recent quiz attempts (last 10)
    attempts_result = await db.execute(
        select(QuizAttempt)
        .where(QuizAttempt.child_id == child_id)
        .order_by(QuizAttempt.created_at.desc())
        .limit(10)
    )
    attempts = attempts_result.scalars().all()

    # Progress per subject
    progress_result = await db.execute(
        select(Progress)
        .where(Progress.child_id == child_id)
        .options(selectinload(Progress.subject))
    )
    progress = progress_result.scalars().all()

    # Earned achievements count
    achievements_count = await db.execute(
        select(func.count()).where(ChildAchievement.child_id == child_id)
    )

    return {
        "child": ChildResponse.model_validate(child),
        "stats": {
            "total_lessons": len(lessons),
            "total_xp": child.xp,
            "streak_days": child.streak_days,
            "achievements_earned": achievements_count.scalar_one(),
        },
        "recent_lessons": [
            {
                "id": l.id,
                "title": l.title,
                "topic": l.topic.title if l.topic else None,
                "xp_reward": l.xp_reward,
                "created_at": l.created_at,
            }
            for l in lessons
        ],
        "recent_attempts": [
            {
                "id": a.id,
                "score": round(a.score * 100),
                "xp_earned": a.xp_earned,
                "created_at": a.created_at,
            }
            for a in attempts
        ],
        "progress": [
            {
                "subject": p.subject.name,
                "subject_emoji": p.subject.emoji,
                "lessons_completed": p.lessons_completed,
                "total_xp": p.total_xp,
            }
            for p in progress
        ],
    }


@router.put("/password")
async def change_own_password(
    data: PasswordChangeOwn,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.current_password, parent.hashed_password):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть не менее 6 символов")
    parent.hashed_password = hash_password(data.new_password)
    await db.flush()
    return {"ok": True}


@router.put("/child/{child_id}/password")
async def change_child_password(
    child_id: int,
    data: PasswordChangeChild,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    child_result = await db.execute(
        select(Child).where(Child.id == child_id, Child.parent_id == parent.id)
    )
    child = child_result.scalar_one_or_none()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть не менее 6 символов")
    child_user_result = await db.execute(select(User).where(User.id == child.user_id))
    child_user = child_user_result.scalar_one_or_none()
    if not child_user:
        raise HTTPException(status_code=404, detail="Child user not found")
    child_user.hashed_password = hash_password(data.new_password)
    await db.flush()
    return {"ok": True}


@router.delete("/child/{child_id}/history")
async def reset_child_history(
    child_id: int,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    """Delete all lessons, quiz attempts, progress and achievements for a child. Reset XP and streak."""
    from app.models.lesson import LessonStep
    from app.models.quiz import Quiz, QuizQuestion
    from app.models.ai_request import AIRequest

    child_result = await db.execute(
        select(Child).where(Child.id == child_id, Child.parent_id == parent.id)
    )
    child = child_result.scalar_one_or_none()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")

    # Collect lesson IDs
    lesson_ids_result = await db.execute(
        select(Lesson.id).where(Lesson.child_id == child_id)
    )
    lesson_ids = lesson_ids_result.scalars().all()

    if lesson_ids:
        # Collect quiz IDs
        quiz_ids_result = await db.execute(
            select(Quiz.id).where(Quiz.lesson_id.in_(lesson_ids))
        )
        quiz_ids = quiz_ids_result.scalars().all()

        if quiz_ids:
            await db.execute(delete(QuizAttempt).where(QuizAttempt.quiz_id.in_(quiz_ids)))
            await db.execute(delete(QuizQuestion).where(QuizQuestion.quiz_id.in_(quiz_ids)))
            await db.execute(delete(Quiz).where(Quiz.id.in_(quiz_ids)))

        await db.execute(delete(LessonStep).where(LessonStep.lesson_id.in_(lesson_ids)))
        await db.execute(delete(AIRequest).where(AIRequest.lesson_id.in_(lesson_ids)))
        await db.execute(delete(Lesson).where(Lesson.child_id == child_id))

    await db.execute(delete(Progress).where(Progress.child_id == child_id))
    await db.execute(delete(ChildAchievement).where(ChildAchievement.child_id == child_id))

    child.xp = 0
    child.streak_days = 0
    child.last_activity_date = None

    await db.flush()
    return {"ok": True, "deleted_lessons": len(lesson_ids)}
