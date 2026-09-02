from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserRead"


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    role: UserRole = UserRole.COORDINATOR
    # Required for FACULTY / STUDENT: the person the account represents.
    faculty_id: int | None = None
    candidate_id: int | None = None
    must_change_password: bool = False


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None
    faculty_id: int | None = None
    candidate_id: int | None = None


class UserRead(ORMModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    must_change_password: bool = False
    faculty_id: int | None = None
    candidate_id: int | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class PasswordResetResponse(BaseModel):
    user: "UserRead"
    temporary_password: str


class ProvisionedAccount(BaseModel):
    """One account created by bulk provisioning, with its one-time password."""

    email: str
    full_name: str
    role: UserRole
    temporary_password: str


class ProvisionResponse(BaseModel):
    created: int = 0
    skipped: int = 0
    accounts: list[ProvisionedAccount] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


Token.model_rebuild()
PasswordResetResponse.model_rebuild()
