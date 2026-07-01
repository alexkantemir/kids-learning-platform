from datetime import datetime, timezone, date

from sqlalchemy import String, ForeignKey, DateTime, Date, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128), default="Учебный план")
    week_start: Mapped[date] = mapped_column(Date)
    week_end: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"))
    child: Mapped["Child"] = relationship("Child")

    items: Mapped[list["PlanItem"]] = relationship("PlanItem", back_populates="plan")


class PlanItem(Base):
    __tablename__ = "plan_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    plan: Mapped["Plan"] = relationship("Plan", back_populates="items")

    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    topic: Mapped["Topic"] = relationship("Topic", back_populates="plan_items")

    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"))
    child: Mapped["Child"] = relationship("Child", back_populates="plan_items")
