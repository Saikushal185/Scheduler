from __future__ import annotations

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import UserRole


class User(Base, TimestampMixin):
    """A login account.

    FACULTY and STUDENT accounts are linked to the person they represent, which
    is what every permission check scopes on: without the link there is nothing
    to narrow their queries to, so the link is required for those two roles.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=32,
             values_callable=lambda e: [m.value for m in e]),
        default=UserRole.ADMIN, nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False)

    faculty_id: Mapped[int | None] = mapped_column(
        ForeignKey("faculty.id", ondelete="CASCADE"), unique=True, index=True)
    candidate_id: Mapped[int | None] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), unique=True, index=True)

    faculty = relationship("Faculty", lazy="selectin")
    candidate = relationship("Candidate", lazy="selectin")
