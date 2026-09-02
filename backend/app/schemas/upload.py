from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import DatasetType, UploadStatus
from app.schemas.common import ORMModel


class RowIssue(BaseModel):
    row: int | None = None
    column: str | None = None
    value: Any | None = None
    message: str


class SheetPreview(BaseModel):
    sheet_name: str
    detected_dataset: DatasetType | None = None
    columns: list[str] = Field(default_factory=list)
    row_count: int = 0
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    missing_required_columns: list[str] = Field(default_factory=list)
    unmapped_columns: list[str] = Field(default_factory=list)
    errors: list[RowIssue] = Field(default_factory=list)
    warnings: list[RowIssue] = Field(default_factory=list)
    is_valid: bool = True


class ValidationResponse(BaseModel):
    upload_id: int
    filename: str
    sheets: list[SheetPreview]
    is_valid: bool
    errors: list[RowIssue] = Field(default_factory=list)


class ImportSummary(BaseModel):
    dataset: DatasetType
    sheet_name: str | None = None
    rows_total: int = 0
    created: int = 0
    updated: int = 0
    failed: int = 0
    errors: list[RowIssue] = Field(default_factory=list)
    warnings: list[RowIssue] = Field(default_factory=list)


class ImportResponse(BaseModel):
    upload_id: int
    filename: str
    status: UploadStatus
    summaries: list[ImportSummary]
    total_created: int = 0
    total_updated: int = 0
    total_failed: int = 0
    free_slots_recalculated: int = 0
    errors: list[RowIssue] = Field(default_factory=list)


class UploadRead(ORMModel):
    id: int
    original_filename: str
    dataset_type: DatasetType | None = None
    status: UploadStatus
    sheet_name: str | None = None
    size_bytes: int
    rows_total: int
    rows_imported: int
    rows_failed: int
    errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class ColumnMapping(BaseModel):
    dataset: DatasetType
    required: list[str]
    optional: list[str] = Field(default_factory=list)
    aliases: dict[str, list[str]] = Field(default_factory=dict)
