import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    ForeignKey,
    Index,
    Integer,
)
from sqlalchemy.orm import relationship

from backend.core.database import Base


# ============================================================
# UTC HELPER
# ============================================================

def utc_now():
    return datetime.now(timezone.utc)


# ============================================================
# SOURCE MODEL
# ============================================================

class Source(Base):
    """
    Core Source model.

    Supports:
    - URL change detection (content_hash)
    - File duplicate detection (file_hash)
    - Re-ingest scheduling
    - Priority refresh categories
    - Crawler tracking (origin + parent)
    - FAQ linking
    - Timeline linking
    """

    __tablename__ = "sources"

    # ---------------------------------------------------------
    # PRIMARY KEY
    # ---------------------------------------------------------

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # ---------------------------------------------------------
    # SOURCE TYPE
    # ---------------------------------------------------------
    # url | pdf | excel | csv | zip

    source_type = Column(String(20), nullable=False, index=True)

    # URL or absolute/local path
    source_value = Column(String, nullable=False, index=True)

    # ---------------------------------------------------------
    # DEDUP / CHANGE DETECTION
    # ---------------------------------------------------------

    file_hash = Column(String(64), nullable=True, index=True)
    content_hash = Column(String(64), nullable=True)

    # ---------------------------------------------------------
    # CLASSIFICATION
    # ---------------------------------------------------------

    category = Column(String(100), nullable=True, index=True)

    # approved | ingested | failed | pending
    status = Column(String(20), default="approved", index=True)

    # ---------------------------------------------------------
    # RE-INGEST CONTROL (NEW)
    # ---------------------------------------------------------

    last_ingested_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    next_reingest_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # dynamic refresh control (optional override)
    refresh_interval_hours = Column(
        Integer,
        nullable=True,
    )

    # manual_priority | high | normal | low
    priority = Column(
        String(20),
        default="normal",
        index=True,
    )

    # ---------------------------------------------------------
    # DISCOVERY TRACKING
    # ---------------------------------------------------------

    # manual | crawl | discovered
    origin = Column(String(20), default="manual", index=True)

    parent_id = Column(
        String(36),
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    parent = relationship(
        "Source",
        remote_side="Source.id",
        backref="children",
        lazy="joined",
    )

    # ---------------------------------------------------------
    # METADATA
    # ---------------------------------------------------------

    language = Column(String(20), nullable=True)

    error_message = Column(Text, nullable=True)

    # ---------------------------------------------------------
    # TIMESTAMPS
    # ---------------------------------------------------------

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # ---------------------------------------------------------
    # RELATIONSHIPS
    # ---------------------------------------------------------

    faqs = relationship(
        "FAQ",
        cascade="all, delete-orphan",
        back_populates="source",
        lazy="selectin",
    )

    timelines = relationship(
        "TimelineEvent",
        cascade="all, delete-orphan",
        back_populates="source",
        lazy="selectin",
    )


# ============================================================
# FAQ MODEL (Auto Generated)
# ============================================================

class FAQ(Base):
    """
    Auto-generated FAQs per source.
    Regenerated when URL content changes.
    """

    __tablename__ = "faqs"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    source_id = Column(
        String(36),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    source = relationship("Source", back_populates="faqs")


# ============================================================
# TIMELINE EVENTS (UPGRADED)
# ============================================================

class TimelineEvent(Base):
    """
    Extracted chronological events.
    Used for admissions, exam dates,
    scholarship deadlines, events, etc.
    """

    __tablename__ = "timeline_events"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    source_id = Column(
        String(36),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Stored as real DateTime for filtering & sorting
    event_date = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    description = Column(Text, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    source = relationship("Source", back_populates="timelines")


# ============================================================
# PERFORMANCE INDEXES
# ============================================================

Index("idx_source_type_status", Source.source_type, Source.status)
Index("idx_source_category_status", Source.category, Source.status)
Index("idx_source_origin_status", Source.origin, Source.status)

Index("idx_source_reingest", Source.next_reingest_at, Source.status)
Index("idx_source_priority", Source.priority, Source.next_reingest_at)
Index("idx_timeline_date", TimelineEvent.event_date)