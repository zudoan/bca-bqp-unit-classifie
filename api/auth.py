"""Registration and cookie-based authentication endpoints."""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from api.database import get_database
from api.models import User, UserSession, utc_now
from api.security import (
    create_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)


router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
SESSION_COOKIE_NAME = "bca_bqp_session"
SHORT_SESSION_HOURS = 12
REMEMBER_SESSION_DAYS = 30
USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]{4,32}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _environment_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


COOKIE_SECURE = _environment_flag("AUTH_COOKIE_SECURE")


class RegistrationRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    username: str = Field(min_length=4, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    remember: bool = True

    @field_validator("display_name", "email", "username")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)
    remember: bool = True

    @field_validator("username")
    @classmethod
    def strip_username(cls, value: str) -> str:
        return value.strip()


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class AuthenticationResponse(BaseModel):
    user: UserResponse
    token: str | None = None


def _normalize_username(value: str) -> str:
    return value.strip().lower()


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _validate_registration(payload: RegistrationRequest) -> tuple[str, str, str]:
    display_name = payload.display_name.strip()
    username = _normalize_username(payload.username)
    email = _normalize_email(payload.email)
    if len(display_name) < 2:
        raise HTTPException(status_code=422, detail="Họ và tên phải có ít nhất 2 ký tự.")
    if not USERNAME_PATTERN.fullmatch(username):
        raise HTTPException(
            status_code=422,
            detail="Tên đăng nhập cần 4–32 ký tự, chỉ gồm chữ thường, số, dấu chấm, gạch dưới hoặc gạch ngang.",
        )
    if not EMAIL_PATTERN.fullmatch(email):
        raise HTTPException(status_code=422, detail="Địa chỉ email chưa hợp lệ.")
    if not re.search(r"[A-Za-z]", payload.password) or not re.search(r"\d", payload.password):
        raise HTTPException(status_code=422, detail="Mật khẩu phải bao gồm ít nhất một chữ và một số.")
    return display_name, username, email


def _create_user_session(database: Session, user: User, remember: bool) -> tuple[str, int | None]:
    now = utc_now()
    database.execute(delete(UserSession).where(UserSession.expires_at <= now))
    token = create_session_token()
    lifetime = timedelta(days=REMEMBER_SESSION_DAYS) if remember else timedelta(hours=SHORT_SESSION_HOURS)
    database.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_session_token(token),
            expires_at=now + lifetime,
        )
    )
    return token, int(lifetime.total_seconds()) if remember else None


def _set_session_cookie(response: Response, token: str, max_age: int | None) -> None:
    is_render = bool(os.getenv("RENDER"))
    secure = COOKIE_SECURE or is_render
    samesite = "none" if secure else "lax"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path="/",
    )


def require_current_user(
    request: Request,
    database: Session = Depends(get_database),
) -> User:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập không tồn tại.")

    session_record = database.scalar(
        select(UserSession)
        .options(joinedload(UserSession.user))
        .where(
            UserSession.token_hash == hash_session_token(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > utc_now(),
        )
    )
    if session_record is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên đăng nhập đã hết hạn.")
    if not session_record.user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản đã bị khóa.")
    return session_record.user


@router.post("/register", response_model=AuthenticationResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegistrationRequest,
    response: Response,
    database: Session = Depends(get_database),
) -> AuthenticationResponse:
    display_name, username, email = _validate_registration(payload)
    duplicate = database.scalar(select(User.id).where(or_(User.username == username, User.email == email)))
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tên đăng nhập hoặc email đã được sử dụng.")

    user = User(
        display_name=display_name,
        username=username,
        email=email,
        password_hash=hash_password(payload.password),
        role="user",
    )
    database.add(user)
    try:
        database.flush()
        token, max_age = _create_user_session(database, user, payload.remember)
        database.commit()
        database.refresh(user)
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tên đăng nhập hoặc email đã được sử dụng.") from error

    _set_session_cookie(response, token, max_age)
    return AuthenticationResponse(user=UserResponse.model_validate(user), token=token)


@router.post("/login", response_model=AuthenticationResponse)
def login(
    payload: LoginRequest,
    response: Response,
    database: Session = Depends(get_database),
) -> AuthenticationResponse:
    user = database.scalar(select(User).where(User.username == _normalize_username(payload.username)))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tên đăng nhập hoặc mật khẩu không chính xác.")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản đã bị khóa.")

    user.last_login_at = utc_now()
    token, max_age = _create_user_session(database, user, payload.remember)
    database.commit()
    database.refresh(user)
    _set_session_cookie(response, token, max_age)
    return AuthenticationResponse(user=UserResponse.model_validate(user), token=token)


@router.get("/me", response_model=AuthenticationResponse)
def me(user: User = Depends(require_current_user)) -> AuthenticationResponse:
    return AuthenticationResponse(user=UserResponse.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    database: Session = Depends(get_database),
) -> None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        session_record = database.scalar(
            select(UserSession).where(
                UserSession.token_hash == hash_session_token(token),
                UserSession.revoked_at.is_(None),
            )
        )
        if session_record:
            session_record.revoked_at = utc_now()
            database.commit()
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
