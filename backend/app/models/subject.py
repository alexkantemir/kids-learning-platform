from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    emoji: Mapped[str] = mapped_column(String(8), default="📚")
    color: Mapped[str] = mapped_column(String(32), default="blue")
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=0)

    topics: Mapped[list["Topic"]] = relationship("Topic", back_populates="subject")
    progress: Mapped[list["Progress"]] = relationship("Progress", back_populates="subject")
