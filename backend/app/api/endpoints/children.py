from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.db.session import get_db
from app.models.user import User, UserRole
from app.models.child import Child
from app.core.security import hash_password
from app.schemas.child import ChildCreate, ChildUpdate, ChildResponse
from app.api.deps import get_current_parent, get_current_user

router = APIRouter()


@router.get("/me", response_model=ChildResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != UserRole.child:
        raise HTTPException(status_code=403, detail="Child account required")
    result = await db.execute(select(Child).where(Child.user_id == current_user.id))
    child = result.scalar_one_or_none()
    if not child:
        raise HTTPException(status_code=404, detail="Child profile not found")
    return child


@router.get("", response_model=list[ChildResponse])
async def list_children(
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Child).where(Child.parent_id == parent.id))
    return result.scalars().all()


@router.post("", response_model=ChildResponse, status_code=status.HTTP_201_CREATED)
async def create_child(
    data: ChildCreate,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.username == data.username.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    child_user = User(
        username=data.username.lower(),
        hashed_password=hash_password(data.password),
        role=UserRole.child,
    )
    db.add(child_user)
    await db.flush()

    child = Child(
        name=data.name,
        age=data.age,
        grade=data.grade,
        avatar_color=data.avatar_color,
        parent_id=parent.id,
        user_id=child_user.id,
    )
    db.add(child)
    await db.flush()
    await db.refresh(child)
    return child


@router.get("/{child_id}/warmup")
async def get_warmup(
    child_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == UserRole.child:
        result = await db.execute(select(Child).where(Child.user_id == current_user.id))
        child = result.scalar_one_or_none()
        if not child or child.id != child_id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        result = await db.execute(
            select(Child).where(Child.id == child_id, Child.parent_id == current_user.id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Child not found")

    sql = text("""
        SELECT
            qq.question,
            qq.options,
            qq.correct_index,
            qq.explanation,
            l.title AS lesson_title
        FROM quiz_questions qq
        JOIN quizzes qz ON qz.id = qq.quiz_id
        JOIN lessons l ON l.id = qz.lesson_id
        WHERE qz.id IN (
            SELECT DISTINCT quiz_id
            FROM quiz_attempts
            WHERE child_id = :child_id
              AND created_at < NOW() - INTERVAL '2 days'
              AND created_at > NOW() - INTERVAL '7 days'
        )
        ORDER BY RANDOM()
        LIMIT 3
    """)
    rows = (await db.execute(sql, {"child_id": child_id})).fetchall()

    return [
        {
            "question": row.question,
            "options": row.options,
            "correct_index": row.correct_index,
            "explanation": row.explanation,
            "lesson_title": row.lesson_title,
        }
        for row in rows
    ]


@router.patch("/{child_id}", response_model=ChildResponse)
async def update_child(
    child_id: int,
    data: ChildUpdate,
    parent: User = Depends(get_current_parent),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Child).where(Child.id == child_id, Child.parent_id == parent.id)
    )
    child = result.scalar_one_or_none()
    if not child:
        raise HTTPException(status_code=404, detail="Child not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(child, field, value)
    await db.flush()
    await db.refresh(child)
    return child
