"""Shared FastAPI dependencies."""
from __future__ import annotations

from typing import Annotated, Callable

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AuthError, PermissionError_
from app.core.permissions import (ADMIN_ROLES, REPORT_ROLES, STAFF_ROLES, Scope,
                                  build_scope)
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


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    """Dependency factory gating an endpoint to a set of roles.

    Use for endpoints a role must not reach at all.  For endpoints everybody may
    call but where the rows must narrow to the caller, depend on `CurrentScope`
    instead and apply the scope to the query.
    """
    allowed = set(roles)

    def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            names = ", ".join(sorted(r.value for r in allowed))
            raise PermissionError_(
                f"Your role ({user.role.value}) cannot perform this action. "
                f"Allowed roles: {names}.")
        return user

    return dependency


def get_scope(user: CurrentUser) -> Scope:
    return build_scope(user)


CurrentScope = Annotated[Scope, Depends(get_scope)]

# Common gates, named for the thing they protect rather than the roles, so call
# sites read as intent.
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
"""Strictly ADMIN - user administration only."""

ManagerUser = Annotated[User, Depends(require_roles(*ADMIN_ROLES))]
"""ADMIN or COORDINATOR - runs the scheduling workflow, uploads, settings."""

StaffUser = Annotated[User, Depends(require_roles(*STAFF_ROLES))]
"""Anyone who works the process - excludes students."""

ReportUser = Annotated[User, Depends(require_roles(*REPORT_ROLES))]
"""Anyone allowed to read institute-wide reporting - excludes students."""
