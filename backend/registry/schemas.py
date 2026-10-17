from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime


# ------------------------------------------------------------------
# Create Source (admin upload / discovered links)
# ------------------------------------------------------------------

class SourceCreate(BaseModel):
    source_type: str               # url | pdf | csv | zip
    source_value: str              # URL or filename
    category: Optional[str] = None
    origin: str                    # admin | discovered
    parent_id: Optional[str] = None


# ------------------------------------------------------------------
# Update Status (single)
# ------------------------------------------------------------------

class SourceUpdateStatus(BaseModel):
    status: str                    # approved | disabled | pending


# ------------------------------------------------------------------
# Update Category (single)
# ------------------------------------------------------------------

class SourceUpdateCategory(BaseModel):
    category: str


# ------------------------------------------------------------------
# Bulk Requests
# ------------------------------------------------------------------

class BulkIdsRequest(BaseModel):
    source_ids: List[str]


class BulkCategoryUpdateRequest(BaseModel):
    source_ids: List[str]
    category: str


# ------------------------------------------------------------------
# Source Response (ADMIN UI + API)
# ------------------------------------------------------------------

class SourceResponse(BaseModel):
    id: str
    source_type: str
    origin: str
    parent_id: Optional[str]

    source_value: str
    category: Optional[str]

    status: str                    # pending | approved | ingested | failed | disabled
    language: Optional[str]

    error_message: Optional[str]   # ✅ WHY ingestion failed

    created_at: datetime
    updated_at: Optional[datetime]
    last_ingested_at: Optional[datetime]

    class Config:
        from_attributes = True


# ------------------------------------------------------------------
# Bulk Ingest Response (Progress Visibility)
# ------------------------------------------------------------------

class BulkIngestFailure(BaseModel):
    id: str
    error: str


class BulkIngestSkipped(BaseModel):
    id: str
    reason: str


class BulkIngestResponse(BaseModel):
    requested: int
    ingested: int
    failed: List[BulkIngestFailure]
    skipped: List[BulkIngestSkipped]
    missing: List[str]
