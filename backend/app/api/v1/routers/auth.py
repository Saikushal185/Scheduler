from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.core.config import settings
from app.core.exceptions import AuthError, NotFoundError, ValidationError
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories import UserRepository
from app.schemas.auth import (ChangePasswordRequest, LoginRequest,
                              PasswordResetResponse, Token, UserCreate, UserRead,
                              UserUpdate)
from app.schemas.common import Message
from app.services.account_service import AccountService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token, summary="Exchange credentials for a JWT")
def login(payload: LoginRequest, db: DbSession) -> Token:
    user = UserRepository(db).by_email(payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise AuthError("Incorrect email or password")
    if not user.is_active:
        raise AuthError("This account has been disabled")
    token = create_access_token(str(user.id), extra={"role": str(user.role),
                                                     "email": user.email})
    return Token(access_token=token,
                 expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                 user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead, summary="Current authenticated user")
def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.post("/change-password", response_model=Message,
             summary="Change your own password")
def change_password(payload: ChangePasswordRequest, db: DbSession,
                    user: CurrentUser) -> Message:
    """Also clears `must_change_password`, which gates first-login accounts."""
    if not verify_password(payload.current_password, user.hashed_password):
        raise AuthError("Your current password is incorrect")
    if payload.new_password == payload.current_password:
        raise ValidationError("The new password must differ from the current one")
    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = False
    db.flush()
    return Message(message="Password updated")


# ------------------------------------------------------------ administration
@router.get("/users", response_model=list[UserRead], summary="List users")
def list_users(db: DbSession, current: AdminUser) -> list[UserRead]:
    return [UserRead.model_validate(u) for u in UserRepository(db).all()]


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED,
             summary="Create a user")
def create_user(payload: UserCreate, db: DbSession, current: AdminUser) -> UserRead:
    return UserRead.model_validate(AccountService(db).create(payload))


@router.put("/users/{user_id}", response_model=UserRead, summary="Update a user")
def update_user(user_id: int, payload: UserUpdate, db: DbSession,
                current: AdminUser) -> UserRead:
    return UserRead.model_validate(AccountService(db).update(user_id, payload))


@router.post("/users/{user_id}/reset-password", response_model=PasswordResetResponse,
             summary="Reset a user's password")
def reset_password(user_id: int, db: DbSession,
                   current: AdminUser) -> PasswordResetResponse:
    """Issues a one-time password the user must change on next sign-in."""
    user, temporary = AccountService(db).reset_password(user_id)
    return PasswordResetResponse(user=UserRead.model_validate(user),
                                 temporary_password=temporary)


@router.delete("/users/{user_id}", response_model=Message, summary="Deactivate a user")
def deactivate_user(user_id: int, db: DbSession, current: AdminUser) -> Message:
    repo = UserRepository(db)
    user = repo.get(user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} was not found")
    if user.id == current.id:
        raise ValidationError("You cannot deactivate your own account")
    user.is_active = False
    db.flush()
    return Message(message=f"User {user.email} deactivated")
