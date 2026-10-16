"""Tables. Migrations only ever add — nothing here drops data."""
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    """One unit of work for the worker (a PDF save, a domain row, a website row).
    `state` keeps per-step progress so a retry resumes at the failed step and never redoes finished ones."""

    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    idem_key: Mapped[str] = mapped_column(String(300))
    resource: Mapped[str | None] = mapped_column(String(100))  # e.g. "nick:n1" — one running job per resource
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|done|failed|blocked|conflict
    step: Mapped[str | None] = mapped_column(String(80))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    locked_by: Mapped[str | None] = mapped_column(String(80))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    __table_args__ = (
        # Anti double-run: at most one live job per idempotency key.
        Index("uq_jobs_live_key", "idem_key", unique=True, postgresql_where=text("status IN ('queued','running')")),
        Index("ix_jobs_claim", "status", "run_after"),
    )


class JobLog(Base):
    __tablename__ = "job_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    level: Mapped[str] = mapped_column(String(10))  # ok|info|warn|err
    message: Mapped[str] = mapped_column(Text)


class SheetWrite(Base):
    """Every cell/row the app writes to Google Sheets — audit trail and undo source."""

    __tablename__ = "sheet_writes"
    id: Mapped[int] = mapped_column(primary_key=True)
    tab: Mapped[str] = mapped_column(String(100))
    range: Mapped[str] = mapped_column(String(60))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str] = mapped_column(Text)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PdfDocument(Base):
    __tablename__ = "pdf_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    md5: Mapped[str] = mapped_column(String(32), unique=True)
    original_name: Mapped[str] = mapped_column(String(300))
    size: Mapped[int] = mapped_column(Integer)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    has_text: Mapped[bool] = mapped_column(Boolean, default=False)
    doc_type: Mapped[str] = mapped_column(String(10), default="unknown")  # wy|ca|br|unknown
    detection_confidence: Mapped[float] = mapped_column(default=0.0)
    detection_reason: Mapped[str] = mapped_column(Text, default="")
    fields: Mapped[dict] = mapped_column(JSON, default=dict)  # {A: {value, source, note}, D..J}
    extra: Mapped[dict] = mapped_column(JSON, default=dict)  # CNAE, situação, etc. (DB only)
    industry: Mapped[dict] = mapped_column(JSON, default=dict)
    # uploaded → extracted|needs_ai → review → queued → saved | failed
    status: Mapped[str] = mapped_column(String(20), default="uploaded")
    error: Mapped[str | None] = mapped_column(Text)
    drive_file_id: Mapped[str | None] = mapped_column(String(200))
    drive_link: Mapped[str | None] = mapped_column(Text)
    sheet_row: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Nick(Base):
    __tablename__ = "nicks"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # n1, n2… (secrets: *_N1 env vars)
    name: Mapped[str] = mapped_column(String(60))
    ip: Mapped[str] = mapped_column(String(45))
    hosting: Mapped[str | None] = mapped_column(String(200))
    cpanel_host: Mapped[str] = mapped_column(String(200))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    weight: Mapped[int] = mapped_column(Integer, default=1)
    daily_limit: Mapped[int | None] = mapped_column(Integer)


class RootDomain(Base):
    __tablename__ = "root_domains"
    name: Mapped[str] = mapped_column(String(253), primary_key=True)
    nick_id: Mapped[str] = mapped_column(ForeignKey("nicks.id"), index=True)
    dns_host: Mapped[str] = mapped_column(String(10))  # inet|cpanel|other|unknown
    expires: Mapped[date | None] = mapped_column(Date)
    apex_on_hosting: Mapped[bool] = mapped_column(Boolean, default=False)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)  # ticked by the owner; nothing pre-ticked
    source: Mapped[str] = mapped_column(String(20), default="seed")  # seed|inet_api


class AppSetting(Base):
    """Small key/value store: queue pause flags, the Drive folder the app created, etc."""

    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
