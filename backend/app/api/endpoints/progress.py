from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.child import Child
from app.models.progress import Progress
from app.api.deps import get_current_user

router = APIRouter()


@router.get("/child/{child_id}")
async def get_progress(
    child_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role == UserRole.child:
        result = await db.execute(select(Child).where(Child.user_id == user.id))
        child = result.scalar_one_or_none()
        if not child or child.id != child_id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        result = await db.execute(
            select(Child).where(Child.id == child_id, Child.parent_id == user.id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Child not found")

    result = await db.execute(
        select(Progress)
        .where(Progress.child_id == child_id)
        .options(selectinload(Progress.subject))
    )
    return result.scalars().all()
