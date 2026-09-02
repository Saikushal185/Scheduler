"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AuthError, PermissionError_
from app.core.security import decode_access_token
from app.models import User
from app.models.enums import UserRole
from app.repositories import UserRepository

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbSession,
                     authorization: Annotated[str | None, Header()] = None) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("Authentication required. Send an 'Authorization: Bearer' header.")
    payload = decode_access_token(authorization.split(" ", 1)[1].strip())
    user_id = payload.get("sub")
    user = UserRepository(db).get(int(user_id)) if user_id else None
    if user is None or not user.is_active:
        raise AuthError("The authenticated user no longer exists or is disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role not in (UserRole.ADMIN, UserRole.COORDINATOR):
        raise PermissionError_("This action requires an administrator account")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
