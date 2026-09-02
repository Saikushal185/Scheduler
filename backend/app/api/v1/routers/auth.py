from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.exceptions import AuthError, ValidationError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.enums import UserRole
from app.repositories import UserRepository
from app.schemas.auth import LoginRequest, Token, UserCreate, UserRead

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


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED,
             summary="Create a user")
def create_user(payload: UserCreate, db: DbSession, current: CurrentUser) -> UserRead:
    if current.role != UserRole.ADMIN:
        raise ValidationError("Only an administrator can create users")
    repo = UserRepository(db)
    if repo.by_email(payload.email):
        raise ValidationError(f"A user with email {payload.email} already exists")
    user = repo.create(email=payload.email.lower(), full_name=payload.full_name,
                       hashed_password=hash_password(payload.password),
                       role=payload.role)
    return UserRead.model_validate(user)


@router.get("/users", response_model=list[UserRead], summary="List users")
def list_users(db: DbSession, current: CurrentUser) -> list[UserRead]:
    return [UserRead.model_validate(u) for u in UserRepository(db).all()]
