from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.child import Child
from app.models.lesson import Lesson
from app.schemas.lesson import LessonGenerateRequest
from app.api.deps import get_current_user
from app.services.lesson_generator import generate_and_save_lesson
from app.services.lesson_pipeline import generate_and_save_lesson_new

router = APIRouter()


async def _get_child_for_user(user: User, child_id: int, db: AsyncSession) -> Child:
    if user.role == UserRole.child:
        result = await db.execute(select(Child).where(Child.user_id == user.id))
        child = result.scalar_one_or_none()
        if not child or child.id != child_id:
            raise HTTPException(status_code=403, detail="Access denied")
        return child
    else:
        result = await db.execute(
            select(Child).where(Child.id == child_id, Child.parent_id == user.id)
        )
        child = result.scalar_one_or_none()
        if not child:
            raise HTTPException(status_code=404, detail="Child not found")
        return child


@router.post("/generate")
async def generate_lesson(
    data: LessonGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new AI lesson for a child. May take 10-30 seconds."""
    await _get_child_for_user(user, data.child_id, db)

    try:
        generator = generate_and_save_lesson_new if settings.USE_NEW_LESSON_PIPELINE else generate_and_save_lesson
        lesson = await generator(
            child_id=data.child_id,
            topic_id=data.topic_id,
            difficulty=data.difficulty,
            db=db,
        )
        return {
            "lesson_id": lesson.id,
            "title": lesson.title,
            "status": lesson.status,
            "xp_reward": lesson.xp_reward,
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"AI generation failed: {str(e)}")


@router.get("/child/{child_id}")
async def list_child_lessons(
    child_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_child_for_user(user, child_id, db)
    result = await db.execute(
        select(Lesson)
        .where(Lesson.child_id == child_id, Lesson.status == "ready")  # needs_review excluded
        .options(selectinload(Lesson.topic))
        .order_by(Lesson.created_at.desc())
    )
    lessons = result.scalars().all()
    return [
        {
            "id": l.id,
            "title": l.title,
            "topic": l.topic.title if l.topic else None,
            "xp_reward": l.xp_reward,
            "created_at": l.created_at,
        }
        for l in lessons
    ]


@router.get("/{lesson_id}")
async def get_lesson(
    lesson_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.quiz import Quiz as QuizModel, QuizQuestion as QuizQuestionModel

    result = await db.execute(
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(
            selectinload(Lesson.steps),
            selectinload(Lesson.quiz).selectinload(QuizModel.questions),
            selectinload(Lesson.topic),
        )
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")

    await _get_child_for_user(user, lesson.child_id, db)

    quiz_data = None
    if lesson.quiz:
        quiz_data = {
            "id": lesson.quiz.id,
            "questions": [
                {
                    "id": q.id,
                    "question": q.question,
                    "options": q.options,
                    "sort_order": q.sort_order,
                }
                for q in lesson.quiz.questions
            ],
        }

    return {
        "id": lesson.id,
        "title": lesson.title,
        "age_band": lesson.age_band,
        "goal": lesson.goal,
        "story_intro": lesson.story_intro,
        "xp_reward": lesson.xp_reward,
        "badge_candidate": lesson.badge_candidate,
        "status": lesson.status,
        "topic": {"id": lesson.topic.id, "title": lesson.topic.title} if lesson.topic else None,
        "steps": [
            {
                "id": s.id,
                "type": s.step_subtype if s.step_subtype else s.step_type.value,
                "title": s.title,
                "content": s.content if s.step_type.value == "explain" else None,
                "explanation": s.content if s.step_type.value == "game" else None,
                "task": s.task,
                "options": s.options,
                "correct_index": s.correct_option_index,
                "sort_order": s.sort_order,
                "feedback_correct": s.feedback_correct,
                "feedback_wrong": s.feedback_wrong,
                "hint": s.hint,
                "step_data": s.step_data,
            }
            for s in lesson.steps
        ],
        "quiz": quiz_data,
        "created_at": lesson.created_at,
    }
