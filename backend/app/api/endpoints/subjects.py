from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.subject import Subject
from app.models.topic import Topic
from app.schemas.subject import SubjectResponse, TopicResponse
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()


class CustomTopicCreate(BaseModel):
    title: str
    subject_id: int
    difficulty: int = 1

    @field_validator("title")
    @classmethod
    def clean_title(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Title must be at least 3 characters")
        if len(v) > 200:
            raise ValueError("Title must be at most 200 characters")
        forbidden = ["http://", "https://", "<script", "javascript:"]
        for bad in forbidden:
            if bad.lower() in v.lower():
                raise ValueError("Invalid topic title")
        return v

    @field_validator("difficulty")
    @classmethod
    def check_difficulty(cls, v: int) -> int:
        if not (1 <= v <= 3):
            raise ValueError("Difficulty must be 1, 2 or 3")
        return v


@router.get("", response_model=list[SubjectResponse])
async def list_subjects(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Subject).where(Subject.is_active == True).order_by(Subject.sort_order)
    )
    return result.scalars().all()


@router.get("/{subject_id}/topics", response_model=list[TopicResponse])
async def list_topics(
    subject_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Topic).where(
            Topic.subject_id == subject_id,
            Topic.is_catalog == True,
            Topic.is_approved == True,
        )
    )
    return result.scalars().all()


@router.post("/topics/custom", response_model=TopicResponse)
async def create_custom_topic(
    data: CustomTopicCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    subject_result = await db.execute(select(Subject).where(Subject.id == data.subject_id))
    if not subject_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Subject not found")

    topic = Topic(
        title=data.title,
        subject_id=data.subject_id,
        difficulty=data.difficulty,
        is_catalog=False,
        is_approved=True,  # Auto-approve for MVP; can add parent approval later
    )
    db.add(topic)
    await db.flush()
    await db.refresh(topic)
    return topic
