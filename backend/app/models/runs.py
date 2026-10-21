"""Feed sources and search run history."""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    badge: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'")
    )

    max_runs_per_day: Mapped[int | None] = mapped_column(Integer)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SearchRun(Base):
    __tablename__ = "search_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'done', 'error')", name="status_valid"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    trigger: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_new: Mapped[int] = mapped_column(Integer, server_default="0")

class SearchRunStep(Base):
    __tablename__ = "search_run_steps"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'done', 'error', 'skipped')",
            name="status_valid",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("search_runs.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    found: Mapped[int] = mapped_column(Integer, server_default="0")
    new: Mapped[int] = mapped_column(Integer, server_default="0")
    message: Mapped[str | None] = mapped_column(Text)
