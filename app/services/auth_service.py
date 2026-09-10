from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.security import (
    hash_password,
    verify_password,
)
from app.models.user import User


DUMMY_PASSWORD_HASH = hash_password(
    "shoeflow-invalid-password"
)


def get_user_by_username(
    db: Session,
    username: str,
) -> User | None:
    """根据用户名查询用户。"""

    normalized_username = username.strip().lower()

    statement = select(User).where(
        User.username == normalized_username
    )

    return db.scalar(statement)


def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> User:
    """验证用户名、密码及账号状态。"""

    user = get_user_by_username(
        db=db,
        username=username,
    )

    if user is None:
        verify_password(
            password,
            DUMMY_PASSWORD_HASH,
        )

        raise AppException(
            message="用户名或密码错误",
            code="INVALID_CREDENTIALS",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not verify_password(
        password,
        user.password_hash,
    ):
        raise AppException(
            message="用户名或密码错误",
            code="INVALID_CREDENTIALS",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        raise AppException(
            message="账号已停用",
            code="USER_INACTIVE",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return user