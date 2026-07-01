from datetime import datetime
from pydantic import BaseModel, field_validator


class ChildCreate(BaseModel):
    name: str
    age: int
    grade: int
    avatar_color: str = "blue"
    username: str  # login for the child's own account
    password: str

    @field_validator("age")
    @classmethod
    def check_age(cls, v: int) -> int:
        if not (5 <= v <= 18):
            raise ValueError("Age must be between 5 and 18")
        return v

    @field_validator("grade")
    @classmethod
    def check_grade(cls, v: int) -> int:
        if not (1 <= v <= 11):
            raise ValueError("Grade must be between 1 and 11")
        return v


class ChildUpdate(BaseModel):
    name: str | None = None
    age: int | None = None
    grade: int | None = None
    avatar_color: str | None = None


class ChildResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    age: int
    grade: int
    avatar_color: str
    xp: int
    streak_days: int
    last_activity_date: datetime | None = None


class ChildWithProgress(ChildResponse):
    total_lessons: int = 0
    total_quizzes: int = 0
