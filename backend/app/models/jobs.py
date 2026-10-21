"""Job listings and their AI scores."""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "source IN ('weworkremotely', 'remoteok', 'remotive', "
            "'linkedin_email', 'extension', 'manual')",
            name="source_valid",
        ),
        CheckConstraint(
            "work_mode IS NULL OR work_mode IN ('remote', 'hybrid', 'on_site')",
            name="work_mode_valid",
        ),
        CheckConstraint(
            "pipeline_status IN ('new', 'filtered_out', 'scored', 'error')",
            name="pipeline_status_valid",
        ),
        # Scoring queue: only jobs waiting to be scored, high priority first,
        # then newest first.
        Index(
            "ix_jobs_scoring_queue",
            text("priority DESC"),
            text("created_at DESC"),
            postgresql_where=text("pipeline_status = 'new'"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    company: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    url_normalized: Mapped[str] = mapped_column(Text, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    work_mode: Mapped[str | None] = mapped_column(Text)
    published: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 0 = normal, 1 = high. Set by code at insert time, based on the source.
    priority: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    pipeline_status: Mapped[str] = mapped_column(
        Text, server_default="new", index=True
    )
    filter_reason: Mapped[str | None] = mapped_column(Text)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class JobScore(Base):
    __tablename__ = "job_scores"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="score_range"),
        # One score per prompt version; re-scoring with a new prompt keeps history.
        UniqueConstraint("job_id", "prompt_version", name="uq_job_scores_job_prompt"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    job_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("jobs.id", ondelete="CASCADE")
    )
    score: Mapped[int] = mapped_column(SmallInteger)
    reason: Mapped[str | None] = mapped_column(Text)
    red_flags: Mapped[list[str] | None] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )