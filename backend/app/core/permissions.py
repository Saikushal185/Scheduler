"""Role-based access control policy.

Two different mechanisms, because two different things need protecting:

* **Gating** - whole endpoints a role may not touch at all (uploads, the
  scheduler, settings, user administration).  The FastAPI dependency that
  enforces this lives in `app.api.deps` (it needs the auth plumbing); the policy
  it reads - which roles count as staff, who may administer - lives here.

* **Scoping** - endpoints everybody may call, but where the *rows* returned must
  narrow to the caller.  A faculty member listing interviews should see their
  own panels, not a 403.  `Scope` carries that narrowing and every list endpoint
  applies it, so one shared page keeps working for every role.

Ownership checks on mutations are the `assert_*` helpers.  They are called from
the service layer, not only the routers, so alternate entry points (the Excel
importer, for instance) cannot bypass them.

This module deliberately imports no FastAPI request plumbing, which keeps the
policy unit-testable on its own.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import PermissionError_
from app.models import User
from app.models.enums import UserRole

# Roles that administer the system.  COORDINATOR is admin-lite: it runs the
# scheduling workflow but may not manage user accounts.
ADMIN_ROLES = (UserRole.ADMIN, UserRole.COORDINATOR)
STAFF_ROLES = (UserRole.ADMIN, UserRole.COORDINATOR, UserRole.FACULTY)
# Roles allowed to read institute-wide reporting.
REPORT_ROLES = (UserRole.ADMIN, UserRole.COORDINATOR, UserRole.FACULTY,
                UserRole.VIEWER)


def is_admin(user: User) -> bool:
    return user.role in ADMIN_ROLES


@dataclass(frozen=True, slots=True)
class Scope:
    """How far a caller may see.

    `faculty_id` / `candidate_id` are set only for roles that must be narrowed;
    an administrator gets an unrestricted scope.
    """

    user: User
    faculty_id: int | None = None
    candidate_id: int | None = None

    @property
    def unrestricted(self) -> bool:
        return self.faculty_id is None and self.candidate_id is None

    @property
    def role(self) -> UserRole:
        return self.user.role

    @property
    def is_admin(self) -> bool:
        return is_admin(self.user)


def build_scope(user: User) -> Scope:
    """Derive the caller's data scope from their role and account links.

    A FACULTY or STUDENT account with no linked person is refused rather than
    silently treated as unrestricted - failing closed is the whole point.
    """
    if is_admin(user) or user.role == UserRole.VIEWER:
        return Scope(user=user)
    if user.role == UserRole.FACULTY:
        if user.faculty_id is None:
            raise PermissionError_(
                "This faculty account is not linked to a faculty record. "
                "Ask an administrator to link it before using the system.")
        return Scope(user=user, faculty_id=user.faculty_id)
    if user.role == UserRole.STUDENT:
        if user.candidate_id is None:
            raise PermissionError_(
                "This student account is not linked to a candidate record. "
                "Ask an administrator to link it before using the system.")
        return Scope(user=user, candidate_id=user.candidate_id)
    raise PermissionError_(f"Unsupported role '{user.role}'")


# ------------------------------------------------------------------ ownership
def assert_faculty_owns(scope: Scope, faculty_id: int | None,
                        what: str = "record") -> None:
    """A faculty user may only modify their own availability / evaluations."""
    if scope.faculty_id is None:
        return  # administrator or viewer-level caller, gated elsewhere
    if faculty_id != scope.faculty_id:
        raise PermissionError_(f"You can only modify your own {what}.")


def assert_candidate_owns(scope: Scope, candidate_id: int | None,
                          what: str = "record") -> None:
    """A student may only act on their own interview."""
    if scope.candidate_id is None:
        return  # not a student-scoped caller
    if candidate_id != scope.candidate_id:
        raise PermissionError_(f"You can only access your own {what}.")
