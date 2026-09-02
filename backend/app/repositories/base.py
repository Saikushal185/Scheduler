"""Generic repository - the single place that talks to the SQLAlchemy session."""
from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    # ----------------------------------------------------------------- queries
    def get(self, obj_id: int) -> ModelT | None:
        return self.db.get(self.model, obj_id)

    def get_by(self, **filters: Any) -> ModelT | None:
        stmt = select(self.model).filter_by(**filters).limit(1)
        return self.db.execute(stmt).scalars().first()

    def list(self, *, skip: int = 0, limit: int | None = 100,
             order_by: Any = None, **filters: Any) -> list[ModelT]:
        stmt: Select = select(self.model)
        if filters:
            stmt = stmt.filter_by(**{k: v for k, v in filters.items() if v is not None})
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        elif hasattr(self.model, "id"):
            stmt = stmt.order_by(self.model.id)
        if skip:
            stmt = stmt.offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def all(self, **filters: Any) -> list[ModelT]:
        return self.list(limit=None, **filters)

    def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model)
        if filters:
            stmt = stmt.filter_by(**{k: v for k, v in filters.items() if v is not None})
        return int(self.db.execute(stmt).scalar_one())

    def exists(self, **filters: Any) -> bool:
        return self.get_by(**filters) is not None

    # ------------------------------------------------------------------ writes
    def create(self, **values: Any) -> ModelT:
        obj = self.model(**values)
        self.db.add(obj)
        self.db.flush()
        return obj

    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.flush()
        return obj

    def bulk_add(self, objs: Sequence[ModelT]) -> list[ModelT]:
        self.db.add_all(list(objs))
        self.db.flush()
        return list(objs)

    def update(self, obj: ModelT, **values: Any) -> ModelT:
        for key, value in values.items():
            if value is not None or key in getattr(self, "nullable_fields", ()):
                setattr(obj, key, value)
        self.db.flush()
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.flush()
