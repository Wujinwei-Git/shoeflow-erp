from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.models.user import UserRole


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(
        min_length=1,
        max_length=64,
    )
    password: str = Field(
        min_length=8,
        max_length=128,
    )

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        cleaned_value = value.strip().lower()

        if not cleaned_value:
            raise ValueError("用户名不能为空")

        return cleaned_value


class UserRead(BaseModel):
    """当前登录用户信息。"""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    username: str
    display_name: str
    role: UserRole
    is_active: bool


class LoginData(BaseModel):
    """登录成功数据。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead