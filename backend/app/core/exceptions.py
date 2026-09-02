"""Domain level exceptions mapped to HTTP responses in app.main."""
from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base class for every expected (non bug) failure."""

    status_code: int = 400
    code: str = "app_error"

    def __init__(self, message: str, *, details: Any = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code

    def to_dict(self) -> dict[str, Any]:
        return {"error": self.code, "message": self.message, "details": self.details}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class AuthError(AppError):
    status_code = 401
    code = "unauthorized"


class PermissionError_(AppError):
    status_code = 403
    code = "forbidden"


class SchedulingError(AppError):
    status_code = 400
    code = "scheduling_error"


class FileValidationError(ValidationError):
    code = "file_validation_error"
