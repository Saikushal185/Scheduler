from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    message: str
    details: Any | None = None


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    skip: int = 0
    limit: int | None = None


class BulkResult(BaseModel):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list)
