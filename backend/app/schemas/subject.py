from pydantic import BaseModel


class SubjectResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str
    slug: str
    emoji: str
    color: str


class TopicResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    description: str | None
    difficulty: int
    is_catalog: bool
    subject_id: int


class TopicCreate(BaseModel):
    title: str
    subject_id: int
    difficulty: int = 1

    @classmethod
    def validate_title(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Topic title too short")
        if len(v) > 200:
            raise ValueError("Topic title too long")
        return v
