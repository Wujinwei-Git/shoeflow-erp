from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """对密码进行不可逆加密。"""

    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """验证输入密码是否正确。"""

    return password_hasher.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(subject: str) -> str:
    """创建登录访问令牌。"""

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        minutes=settings.access_token_expire_minutes,
    )

    payload = {
        "sub": subject,
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(
    token: str,
) -> dict[str, Any]:
    """验证并解析登录访问令牌。"""

    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )