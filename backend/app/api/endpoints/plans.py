from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.child import Child
from app.models.plan import Plan, PlanItem
from app.models.topic import Topic
from app.api.deps import get_current_user

router = APIRouter()


class PlanItemCreate(BaseModel):
    topic_id: int
    sort_order: int = 0


class PlanCreate(BaseModel):
    child_id: int
    week_start: date
    items: list[PlanItemCreate] = []


@router.get("/child/{child_id}/current")
async def get_current_plan(
    child_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify access
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

    today = date.today()
    result = await db.execute(
        select(Plan)
        .where(Plan.child_id == child_id, Plan.week_end >= today)
        .options(
            selectinload(Plan.items).selectinload(PlanItem.topic)
        )
        .order_by(Plan.week_start.desc())
        .limit(1)
    )
    plan = result.scalar_one_or_none()

    if not plan:
        return {"plan": None, "items": []}

    return {
        "plan": {
            "id": plan.id,
            "title": plan.title,
            "week_start": plan.week_start,
            "week_end": plan.week_end,
        },
        "items": [
            {
                "id": item.id,
                "topic_id": item.topic_id,
                "topic_title": item.topic.title if item.topic else None,
                "is_completed": item.is_completed,
                "sort_order": item.sort_order,
            }
            for item in sorted(plan.items, key=lambda x: x.sort_order)
        ],
    }


@router.post("/child/{child_id}")
async def create_plan(
    child_id: int,
    data: PlanCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Only parent can create plans
    if user.role != UserRole.parent:
        raise HTTPException(status_code=403, detail="Parent access required")

    child_result = await db.execute(
        select(Child).where(Child.id == child_id, Child.parent_id == user.id)
    )
    if not child_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Child not found")

    week_end = data.week_start + timedelta(days=6)
    plan = Plan(
        child_id=child_id,
        week_start=data.week_start,
        week_end=week_end,
    )
    db.add(plan)
    await db.flush()

    for item_data in data.items:
        item = PlanItem(
            plan_id=plan.id,
            topic_id=item_data.topic_id,
            child_id=child_id,
            sort_order=item_data.sort_order,
        )
        db.add(item)

    await db.flush()
    return {"plan_id": plan.id, "message": "Plan created"}
