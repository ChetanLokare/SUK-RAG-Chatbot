import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    Boolean,
    Integer,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.core.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class SectionVersion(Base):
    __tablename__ = "section_versions"

    __table_args__ = (
        UniqueConstraint(
            "source_id",
            "section_key",
            "version",
            name="uq_section_version",
        ),
    )

    id = Column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    source_id = Column(
        String,
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # section_0, section_1 etc
    section_key = Column(String, nullable=False)

    # Incrementing version number
    version = Column(Integer, nullable=False)

    content_hash = Column(String, nullable=False, index=True)

    content = Column(Text, nullable=False)

    # Only one active version per section_key
    is_active = Column(Boolean, default=True)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    source = relationship("Source", back_populates="sections")
