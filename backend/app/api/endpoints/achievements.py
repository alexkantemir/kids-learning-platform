from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.child import Child
from app.models.achievement import Achievement, ChildAchievement
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/child/{child_id}")
async def get_child_achievements(
    child_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role == UserRole.child:
        child_result = await db.execute(select(Child).where(Child.user_id == user.id))
        child = child_result.scalar_one_or_none()
        if not child or child.id != child_id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        child_result = await db.execute(
            select(Child).where(Child.id == child_id, Child.parent_id == user.id)
        )
        if not child_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Child not found")

    # All achievements with earned status
    all_achievements = await db.execute(select(Achievement))
    all_achievements = all_achievements.scalars().all()

    earned_result = await db.execute(
        select(ChildAchievement)
        .where(ChildAchievement.child_id == child_id)
        .options(selectinload(ChildAchievement.achievement))
    )
    earned = {ca.achievement_id: ca.earned_at for ca in earned_result.scalars().all()}

    return [
        {
            "id": a.id,
            "slug": a.slug,
            "title": a.title,
            "description": a.description,
            "emoji": a.emoji,
            "xp_bonus": a.xp_bonus,
            "earned": a.id in earned,
            "earned_at": earned.get(a.id),
        }
        for a in all_achievements
    ]
