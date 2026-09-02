from __future__ import annotations

from sqlalchemy import (Boolean, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class PanelGroup(Base, TimestampMixin):
    __tablename__ = "panel_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    panel_code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    panel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    department: Mapped[str | None] = mapped_column(String(128), index=True)
    minimum_panel_size: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    maximum_panel_size: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    members = relationship("PanelMember", back_populates="panel",
                           cascade="all, delete-orphan", lazy="selectin")
    interviews = relationship("Interview", back_populates="panel")


class PanelMember(Base, TimestampMixin):
    __tablename__ = "panel_members"
    __table_args__ = (
        UniqueConstraint("panel_id", "faculty_id", name="uq_panel_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    panel_id: Mapped[int] = mapped_column(
        ForeignKey("panel_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    faculty_id: Mapped[int] = mapped_column(
        ForeignKey("faculty.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(64), default="MEMBER", nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    panel = relationship("PanelGroup", back_populates="members")
    faculty = relationship("Faculty", back_populates="panel_memberships", lazy="selectin")
