from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AllowedSender(Base):
    __tablename__ = "allowed_senders"
    __table_args__ = (
        CheckConstraint("kind IN ('job_alert', 'application')", name="kind_valid"),
        UniqueConstraint("sender", "kind", name="uq_allowed_senders_sender_kind"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    sender: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class Email(Base):
    __tablename__ = "emails"
    __table_args__ = (
        CheckConstraint("kind IN ('job_alert', 'application')", name="kind_valid"),
        CheckConstraint(
            "status IN ('unprocessed', 'processed', 'error')", name="status_valid"
        ),
        CheckConstraint(
            '"class" IS NULL OR "class" IN ('
            "'confirmation', 'interview', 'assessment', "
            "'info_request', 'rejection', 'offer')",
            name="class_valid",
        ),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 100",
            name="confidence_valid",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    gmail_message_id: Mapped[str] = mapped_column(Text, unique=True)
    kind: Mapped[str] = mapped_column(Text)
    sender: Mapped[str] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(
        Text, server_default="unprocessed", index=True
    )
    email_class: Mapped[str | None] = mapped_column("class", Text)
    confidence: Mapped[int | None] = mapped_column(SmallInteger)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    application_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("applications.id", ondelete="SET NULL"), index=True
    )
    error: Mapped[str | None] = mapped_column(Text)