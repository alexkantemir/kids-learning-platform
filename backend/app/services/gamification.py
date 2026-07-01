import logging
from datetime import datetime, timezone, date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.child import Child
from app.models.progress import Progress
from app.models.achievement import Achievement, ChildAchievement
from app.models.lesson import Lesson
from app.models.attempt import QuizAttempt

logger = logging.getLogger(__name__)

ACHIEVEMENT_DEFINITIONS = [
    {"slug": "first-lesson", "title": "Первый урок!", "description": "Пройди свой первый урок", "emoji": "🌟", "xp_bonus": 10},
    {"slug": "five-lessons", "title": "Пять уроков", "description": "Пройди 5 уроков", "emoji": "📚", "xp_bonus": 25},
    {"slug": "ten-lessons", "title": "Десять уроков", "description": "Пройди 10 уроков", "emoji": "🎓", "xp_bonus": 50},
    {"slug": "perfect-quiz", "title": "Отличник!", "description": "Получи 100% в тесте", "emoji": "💯", "xp_bonus": 30},
    {"slug": "streak-3", "title": "3 дня подряд", "description": "Занимайся 3 дня подряд", "emoji": "🔥", "xp_bonus": 20},
    {"slug": "streak-7", "title": "Неделя знаний", "description": "Занимайся 7 дней подряд", "emoji": "🏆", "xp_bonus": 70},
    {"slug": "math-explorer", "title": "Математик", "description": "Пройди 3 урока по математике", "emoji": "🔢", "xp_bonus": 30},
    {"slug": "first-100-xp", "title": "100 очков!", "description": "Набери 100 XP", "emoji": "⭐", "xp_bonus": 0},
    {"slug": "first-500-xp", "title": "500 очков!", "description": "Набери 500 XP", "emoji": "🌠", "xp_bonus": 0},
]


async def ensure_achievements_exist(db: AsyncSession) -> None:
    """Seed achievement definitions if not present."""
    for definition in ACHIEVEMENT_DEFINITIONS:
        existing = await db.execute(
            select(Achievement).where(Achievement.slug == definition["slug"])
        )
        if not existing.scalar_one_or_none():
            achievement = Achievement(**definition)
            db.add(achievement)
    await db.flush()


async def update_streak(child: Child) -> None:
    """Update streak counter based on last activity date."""
    today = date.today()
    if child.last_activity_date:
        last_date = child.last_activity_date.date() if hasattr(child.last_activity_date, 'date') else child.last_activity_date
        if last_date == today:
            return  # already updated today
        elif last_date == today - timedelta(days=1):
            child.streak_days += 1
        else:
            child.streak_days = 1  # streak broken
    else:
        child.streak_days = 1
    child.last_activity_date = datetime.now(timezone.utc)


async def check_and_award_achievements(child: Child, db: AsyncSession) -> list[str]:
    """Check if child earned any new achievements. Returns list of newly earned slugs."""
    earned_result = await db.execute(
        select(ChildAchievement.achievement_id).where(ChildAchievement.child_id == child.id)
    )
    already_earned_ids = set(earned_result.scalars().all())

    lessons_count = await db.execute(
        select(func.count()).where(Lesson.child_id == child.id, Lesson.status == "ready")
    )
    total_lessons = lessons_count.scalar_one()

    perfect_quiz = await db.execute(
        select(func.count()).where(QuizAttempt.child_id == child.id, QuizAttempt.score == 1.0)
    )
    has_perfect = perfect_quiz.scalar_one() > 0

    newly_earned = []
    checks = [
        ("first-lesson", total_lessons >= 1),
        ("five-lessons", total_lessons >= 5),
        ("ten-lessons", total_lessons >= 10),
        ("perfect-quiz", has_perfect),
        ("streak-3", child.streak_days >= 3),
        ("streak-7", child.streak_days >= 7),
        ("first-100-xp", child.xp >= 100),
        ("first-500-xp", child.xp >= 500),
    ]

    for slug, condition in checks:
        if not condition:
            continue
        achievement = await db.execute(select(Achievement).where(Achievement.slug == slug))
        achievement = achievement.scalar_one_or_none()
        if not achievement or achievement.id in already_earned_ids:
            continue

        child_achievement = ChildAchievement(child_id=child.id, achievement_id=achievement.id)
        db.add(child_achievement)
        child.xp += achievement.xp_bonus
        newly_earned.append(slug)

    await db.flush()
    return newly_earned


async def update_subject_progress(
    child_id: int, subject_id: int, xp_earned: int, db: AsyncSession
) -> None:
    """Update or create progress record for a child+subject combination."""
    result = await db.execute(
        select(Progress).where(
            Progress.child_id == child_id, Progress.subject_id == subject_id
        )
    )
    progress = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if progress:
        progress.total_xp += xp_earned
        progress.lessons_completed += 1
        progress.last_activity = now
    else:
        progress = Progress(
            child_id=child_id,
            subject_id=subject_id,
            total_xp=xp_earned,
            lessons_completed=1,
            last_activity=now,
        )
        db.add(progress)
    await db.flush()
