from typing import NoReturn

from fastapi import Depends, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User


bearer_scheme = HTTPBearer(
    auto_error=False,
)


def raise_unauthorized() -> NoReturn:
    """抛出未登录异常。"""

    raise AppException(
        message="登录状态无效或已过期",
        code="UNAUTHORIZED",
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
    """根据 Bearer Token 获取当前用户。"""

    if credentials is None:
        raise_unauthorized()

    if credentials.scheme.lower() != "bearer":
        raise_unauthorized()

    try:
        payload = decode_access_token(
            credentials.credentials
        )
    except InvalidTokenError:
        raise_unauthorized()

    if payload.get("type") != "access":
        raise_unauthorized()

    subject = payload.get("sub")

    if (
        not isinstance(subject, str)
        or not subject.isdigit()
    ):
        raise_unauthorized()

    user = db.get(
        User,
        int(subject),
    )

    if user is None:
        raise_unauthorized()

    if not user.is_active:
        raise AppException(
            message="账号已停用",
            code="USER_INACTIVE",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return user