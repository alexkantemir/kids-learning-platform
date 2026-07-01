from datetime import datetime, timezone

from sqlalchemy import String, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    emoji: Mapped[str] = mapped_column(String(8), default="🏆")
    xp_bonus: Mapped[int] = mapped_column(default=0)

    earned_by: Mapped[list["ChildAchievement"]] = relationship("ChildAchievement", back_populates="achievement")


class ChildAchievement(Base):
    __tablename__ = "child_achievements"

    id: Mapped[int] = mapped_column(primary_key=True)
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"))
    child: Mapped["Child"] = relationship("Child", back_populates="achievements")

    achievement_id: Mapped[int] = mapped_column(ForeignKey("achievements.id"))
    achievement: Mapped["Achievement"] = relationship("Achievement", back_populates="earned_by")
