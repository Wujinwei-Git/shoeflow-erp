from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.responses import success_response
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginData,
    LoginRequest,
    UserRead,
)
from app.services.auth_service import authenticate_user


router = APIRouter(
    prefix="/auth",
)


@router.post(
    "/login",
    summary="账号登录",
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user = authenticate_user(
        db=db,
        username=payload.username,
        password=payload.password,
    )

    login_data = LoginData(
        access_token=create_access_token(
            subject=str(user.id)
        ),
        expires_in=(
            settings.access_token_expire_minutes
            * 60
        ),
        user=UserRead.model_validate(user),
    )

    return success_response(
        data=login_data.model_dump(mode="json"),
        message="登录成功",
    )


@router.get(
    "/me",
    summary="查询当前登录用户",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    return success_response(
        data=(
            UserRead
            .model_validate(current_user)
            .model_dump(mode="json")
        ),
    )