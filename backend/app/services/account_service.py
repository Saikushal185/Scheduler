"""Login account management and bulk provisioning.

Accounts come from two places and both land here:

* an administrator creating one at a time on the Users page, and
* bulk provisioning from an imported faculty/candidate sheet, which reuses the
  email already present in that data.

Both paths enforce the same rule: a FACULTY or STUDENT account must be linked to
the person it represents, because every permission scope is derived from that
link.  An unlinked account of those roles is refused at creation rather than
failing confusingly at sign-in.
"""
from __future__ import annotations

import secrets
import string
from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from app.core.security import hash_password
from app.models import Candidate, Faculty, User
from app.models.enums import UserRole
from app.repositories import (CandidateRepository, FacultyRepository,
                              UserRepository)
from app.schemas.auth import ClaimAccountRequest, UserCreate, UserUpdate

logger = get_logger(__name__)

# Character set, not a credential: O/0 and l/1/I are left out so a temporary
# password that gets printed or read aloud can be typed back correctly.
_UNAMBIGUOUS_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"


def generate_password(length: int = 10) -> str:
    """A fresh temporary password, drawn from the CSPRNG, never stored in clear."""
    return "".join(secrets.choice(_UNAMBIGUOUS_CHARS) for _ in range(length))


class AccountService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.faculty = FacultyRepository(db)
        self.candidates = CandidateRepository(db)

    # ------------------------------------------------------------------ rules
    def _validate_link(self, role: UserRole, faculty_id: int | None,
                       candidate_id: int | None) -> None:
        if role == UserRole.FACULTY:
            if faculty_id is None:
                raise ValidationError(
                    "A faculty account must be linked to a faculty member "
                    "(faculty_id). Their permissions are scoped to that record.")
            if self.faculty.get(faculty_id) is None:
                raise NotFoundError(f"Faculty {faculty_id} was not found")
        elif role == UserRole.STUDENT:
            if candidate_id is None:
                raise ValidationError(
                    "A student account must be linked to a candidate "
                    "(candidate_id). Their permissions are scoped to that record.")
            if self.candidates.get(candidate_id) is None:
                raise NotFoundError(f"Candidate {candidate_id} was not found")
        elif faculty_id is not None or candidate_id is not None:
            raise ValidationError(
                f"A {role.value} account is institute-wide and must not be linked "
                "to a single faculty member or candidate.")

    def _assert_link_free(self, *, faculty_id: int | None, candidate_id: int | None,
                          exclude_user_id: int | None = None) -> None:
        """One login per person - the FK is unique, fail with a clear message."""
        for column, value, label in (("faculty_id", faculty_id, "faculty member"),
                                     ("candidate_id", candidate_id, "candidate")):
            if value is None:
                continue
            existing = self.users.by_link(**{column: value})
            if existing and existing.id != exclude_user_id:
                raise ValidationError(
                    f"That {label} already has the account {existing.email}.")

    # ----------------------------------------------------------------- CRUD
    def create(self, payload: UserCreate) -> User:
        email = payload.email.lower()
        if self.users.by_email(email):
            raise ValidationError(f"A user with email {email} already exists")
        self._validate_link(payload.role, payload.faculty_id, payload.candidate_id)
        self._assert_link_free(faculty_id=payload.faculty_id,
                               candidate_id=payload.candidate_id)
        user = self.users.create(
            email=email, full_name=payload.full_name,
            hashed_password=hash_password(payload.password), role=payload.role,
            faculty_id=payload.faculty_id, candidate_id=payload.candidate_id,
            must_change_password=payload.must_change_password,
            password_issued_at=datetime.now() if payload.must_change_password else None,
            password_changed_at=None if payload.must_change_password else datetime.now())
        logger.info("Created %s account %s", payload.role.value, email)
        return user

    def update(self, user_id: int, payload: UserUpdate) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} was not found")
        data = payload.model_dump(exclude_unset=True)
        role = data.get("role", user.role)
        faculty_id = data.get("faculty_id", user.faculty_id)
        candidate_id = data.get("candidate_id", user.candidate_id)
        # Changing role away from FACULTY/STUDENT drops the now-meaningless link.
        if role not in (UserRole.FACULTY, UserRole.STUDENT):
            faculty_id = candidate_id = None
        elif role == UserRole.FACULTY:
            candidate_id = None
        elif role == UserRole.STUDENT:
            faculty_id = None
        self._validate_link(role, faculty_id, candidate_id)
        self._assert_link_free(faculty_id=faculty_id, candidate_id=candidate_id,
                               exclude_user_id=user.id)
        for key, value in data.items():
            if key not in ("faculty_id", "candidate_id", "role"):
                setattr(user, key, value)
        user.role = role
        user.faculty_id = faculty_id
        user.candidate_id = candidate_id
        self.db.flush()
        return user

    def reset_password(self, user_id: int) -> tuple[User, str]:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} was not found")
        temporary = generate_password()
        user.hashed_password = hash_password(temporary)
        user.must_change_password = True
        user.password_issued_at = datetime.now()
        user.password_changed_at = None
        self.db.flush()
        logger.info("Reset password for %s", user.email)
        return user, temporary

    # ------------------------------------------------------------------ claim
    def claim(self, payload: ClaimAccountRequest) -> User:
        """Create a login for a person the institute already has on file.

        The code and the email must both match the same record, which is what
        stops someone claiming an account from a code alone. The role follows
        from which kind of record matched, so a claimed account is always
        scoped the same way an admin-created one would be.
        """
        code = payload.code.strip()
        email = payload.email.lower().strip()

        faculty = self.faculty.by_code(code)
        candidate = None if faculty else self.candidates.by_code(code)
        person = faculty or candidate
        # One generic message for a bad code and a mismatched email, so this
        # cannot be used to discover which codes exist.
        if person is None or (person.email or "").lower().strip() != email:
            raise ValidationError(
                "No record matches that code and email address. Check both "
                "against the details your institute holds, or ask an "
                "administrator to set your account up.")

        link_field = "faculty_id" if faculty else "candidate_id"
        role = UserRole.FACULTY if faculty else UserRole.STUDENT
        if self.users.by_link(**{link_field: person.id}):
            raise ValidationError(
                "That record already has an account. Sign in instead, or ask an "
                "administrator to reset the password.")
        if self.users.by_email(email):
            raise ValidationError(
                "That email address is already in use by another account.")

        name = (person.faculty_name if faculty else person.candidate_name)
        user = self.users.create(
            email=email, full_name=name,
            hashed_password=hash_password(payload.password), role=role,
            must_change_password=False, password_changed_at=datetime.now(),
            **{link_field: person.id})
        logger.info("Account claimed for %s by %s", code, email)
        return user

    # ---------------------------------------------------------- provisioning
    def provision_faculty(self, faculty: Sequence[Faculty]) -> dict:
        return self._provision(
            people=faculty, role=UserRole.FACULTY, link_field="faculty_id",
            name_of=lambda f: f.faculty_name, code_of=lambda f: f.faculty_code)

    def provision_candidates(self, candidates: Sequence[Candidate]) -> dict:
        return self._provision(
            people=candidates, role=UserRole.STUDENT, link_field="candidate_id",
            name_of=lambda c: c.candidate_name, code_of=lambda c: c.candidate_code)

    def _provision(self, *, people: Iterable, role: UserRole, link_field: str,
                   name_of, code_of) -> dict:
        """Create one login per person that does not already have one.

        Never overwrites an existing account or password - re-importing a sheet
        is therefore safe and simply reports what it skipped.
        """
        created: list[dict] = []
        skipped = 0
        notes: list[str] = []
        for person in people:
            if self.users.by_link(**{link_field: person.id}):
                skipped += 1
                continue
            email = (person.email or "").strip().lower()
            if not email:
                skipped += 1
                notes.append(f"{code_of(person)} has no email address - skipped")
                continue
            if self.users.by_email(email):
                skipped += 1
                notes.append(f"{email} is already used by another account - skipped")
                continue
            temporary = generate_password()
            self.users.create(
                email=email, full_name=name_of(person),
                hashed_password=hash_password(temporary), role=role,
                must_change_password=True, password_issued_at=datetime.now(),
                **{link_field: person.id})
            created.append({"email": email, "full_name": name_of(person),
                            "role": role, "temporary_password": temporary})
        self.db.flush()
        logger.info("Provisioned %s %s account(s), skipped %s",
                    len(created), role.value, skipped)
        return {"created": len(created), "skipped": skipped,
                "accounts": created, "notes": notes[:50]}
