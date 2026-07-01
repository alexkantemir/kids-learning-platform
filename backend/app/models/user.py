import enum
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    parent = "parent"
    child = "child"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.parent)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationship: parent user → children profiles
    children: Mapped[list["Child"]] = relationship(
        "Child", back_populates="parent", foreign_keys="Child.parent_id"
    )
    # Relationship: child user → child profile
    child_profile: Mapped["Child | None"] = relationship(
        "Child", back_populates="user_account", foreign_keys="Child.user_id", uselist=False
    )
