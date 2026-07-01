from datetime import datetime, timezone

from sqlalchemy import String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Child(Base):
    __tablename__ = "children"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    age: Mapped[int] = mapped_column(Integer)
    grade: Mapped[int] = mapped_column(Integer)
    avatar_color: Mapped[str] = mapped_column(String(32), default="blue")
    xp: Mapped[int] = mapped_column(Integer, default=0)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Parent user who manages this child profile
    parent_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    parent: Mapped["User"] = relationship("User", back_populates="children", foreign_keys=[parent_id])

    # The child's own login account
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    user_account: Mapped["User | None"] = relationship(
        "User", back_populates="child_profile", foreign_keys=[user_id]
    )

    lessons: Mapped[list["Lesson"]] = relationship("Lesson", back_populates="child")
    progress: Mapped[list["Progress"]] = relationship("Progress", back_populates="child")
    achievements: Mapped[list["ChildAchievement"]] = relationship("ChildAchievement", back_populates="child")
    plan_items: Mapped[list["PlanItem"]] = relationship("PlanItem", back_populates="child")
