"""Administrative user-management endpoints and first-admin bootstrap."""
from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.auth import EMAIL_PATTERN, USERNAME_PATTERN, UserResponse, require_current_user
from api.database import SessionLocal, get_database
from api.models import User, UserSession, utc_now
from api.security import hash_password


router = APIRouter(prefix="/api/v1/admin", tags=["User administration"])


class AdminUserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: str | None = Field(default=None, min_length=5, max_length=254)
    role: Literal["admin", "user"] | None = None
    is_active: bool | None = None

    @field_validator("display_name", "email")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    active_count: int
    inactive_count: int
    admin_count: int


def require_admin(user: User = Depends(require_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền quản trị người dùng.")
    return user


def _active_admin_count(database: Session) -> int:
    return int(database.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True))) or 0)


def _protect_last_admin(database: Session, target: User, *, next_role: str, next_active: bool) -> None:
    removes_admin_access = target.role == "admin" and target.is_active and (next_role != "admin" or not next_active)
    if removes_admin_access and _active_admin_count(database) <= 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hệ thống phải còn ít nhất một quản trị viên đang hoạt động.")


def ensure_bootstrap_admin(database: Session) -> User | None:
    """Create or promote the administrator declared through environment variables."""

    username = os.getenv("ADMIN_USERNAME", "").strip().lower()
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    display_name = os.getenv("ADMIN_DISPLAY_NAME", "Quản trị viên hệ thống").strip()
    configured_values = [username, email, password]
    if not any(configured_values):
        return None
    if not all(configured_values):
        raise RuntimeError("ADMIN_USERNAME, ADMIN_EMAIL và ADMIN_PASSWORD phải được cấu hình cùng nhau.")
    if not USERNAME_PATTERN.fullmatch(username):
        raise RuntimeError("ADMIN_USERNAME không đúng định dạng.")
    if not EMAIL_PATTERN.fullmatch(email):
        raise RuntimeError("ADMIN_EMAIL không đúng định dạng.")
    if len(password) < 8 or not any(character.isalpha() for character in password) or not any(character.isdigit() for character in password):
        raise RuntimeError("ADMIN_PASSWORD phải có ít nhất 8 ký tự, bao gồm chữ và số.")
    if len(display_name) < 2:
        raise RuntimeError("ADMIN_DISPLAY_NAME phải có ít nhất 2 ký tự.")

    matches = database.scalars(select(User).where(or_(User.username == username, User.email == email))).all()
    if len(matches) > 1 or (matches and (matches[0].username != username or matches[0].email != email)):
        raise RuntimeError("ADMIN_USERNAME hoặc ADMIN_EMAIL đang thuộc một tài khoản khác.")
    if matches:
        admin = matches[0]
        admin.role = "admin"
        admin.is_active = True
        admin.display_name = display_name
    else:
        admin = User(
            username=username,
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
        )
        database.add(admin)
    database.commit()
    database.refresh(admin)
    return admin


def initialize_admin_account() -> None:
    with SessionLocal() as database:
        ensure_bootstrap_admin(database)


@router.get("/users", response_model=UserListResponse)
def list_users(
    query: str = Query(default="", max_length=120),
    role: Literal["admin", "user"] | None = None,
    is_active: bool | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    _admin: User = Depends(require_admin),
    database: Session = Depends(get_database),
) -> UserListResponse:
    filters = []
    search_text = query.strip().lower()
    if search_text:
        pattern = f"%{search_text}%"
        filters.append(or_(func.lower(User.display_name).like(pattern), func.lower(User.username).like(pattern), func.lower(User.email).like(pattern)))
    if role is not None:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))

    total = int(database.scalar(select(func.count()).select_from(User).where(*filters)) or 0)
    users = database.scalars(
        select(User).where(*filters).order_by(User.created_at.desc()).offset(offset).limit(limit)
    ).all()
    active_count = int(database.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0)
    admin_count = int(database.scalar(select(func.count()).select_from(User).where(User.role == "admin")) or 0)
    all_count = int(database.scalar(select(func.count()).select_from(User)) or 0)
    return UserListResponse(
        items=[UserResponse.model_validate(user) for user in users],
        total=total,
        active_count=active_count,
        inactive_count=all_count - active_count,
        admin_count=admin_count,
    )


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: AdminUserUpdate,
    admin: User = Depends(require_admin),
    database: Session = Depends(get_database),
) -> UserResponse:
    target = database.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản.")

    next_role = payload.role if payload.role is not None else target.role
    next_active = payload.is_active if payload.is_active is not None else target.is_active
    if target.id == admin.id and (next_role != target.role or next_active != target.is_active):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bạn không thể tự thay đổi quyền hoặc khóa tài khoản của mình.")
    _protect_last_admin(database, target, next_role=next_role, next_active=next_active)

    if payload.email is not None:
        normalized_email = payload.email.lower()
        if not EMAIL_PATTERN.fullmatch(normalized_email):
            raise HTTPException(status_code=422, detail="Địa chỉ email chưa hợp lệ.")
        target.email = normalized_email
    if payload.display_name is not None:
        target.display_name = payload.display_name
    target.role = next_role
    target.is_active = next_active
    if not next_active:
        database.execute(
            update(UserSession)
            .where(UserSession.user_id == target.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )

    try:
        database.commit()
        database.refresh(target)
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email đã được tài khoản khác sử dụng.") from error
    return UserResponse.model_validate(target)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_user(
    user_id: str,
    admin: User = Depends(require_admin),
    database: Session = Depends(get_database),
) -> Response:
    target = database.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản.")
    if target.id == admin.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bạn không thể tự khóa tài khoản của mình.")
    _protect_last_admin(database, target, next_role=target.role, next_active=False)
    target.is_active = False
    database.execute(
        update(UserSession)
        .where(UserSession.user_id == target.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    database.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
