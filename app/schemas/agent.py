from datetime import datetime
from decimal import Decimal
from typing import Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.agent import (
    AgentActionStatus,
    AgentActionType,
)


class AgentChatRequest(BaseModel):
    """Agent 对话请求。"""

    message: str = Field(
        min_length=1,
        max_length=2000,
        description="用户输入的自然语言指令",
    )

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("消息不能为空")

        return cleaned_value


class AgentQueryArguments(BaseModel):
    """SKU 与库存查询工具的统一参数。"""

    model_config = ConfigDict(
        extra="forbid",
    )

    local_sku: str | None = Field(
        default=None,
        max_length=32,
    )
    barcode: str | None = Field(
        default=None,
        max_length=64,
    )
    brand: str | None = Field(
        default=None,
        max_length=100,
    )
    article_number: str | None = Field(
        default=None,
        max_length=100,
    )
    size: str | None = Field(
        default=None,
        max_length=32,
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=50,
    )

    @field_validator(
        "local_sku",
        "brand",
        "article_number",
        "size",
    )
    @classmethod
    def normalize_business_value(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned_value = value.strip().upper()
        return cleaned_value or None

    @field_validator("barcode")
    @classmethod
    def normalize_barcode(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned_value = value.strip()
        return cleaned_value or None


class AgentSalePreviewArguments(BaseModel):
    """自然语言销售预览工具参数。"""

    model_config = ConfigDict(
        extra="forbid",
    )

    local_sku: str | None = Field(
        default=None,
        max_length=32,
    )
    barcode: str | None = Field(
        default=None,
        max_length=64,
    )
    brand: str | None = Field(
        default=None,
        max_length=100,
    )
    article_number: str | None = Field(
        default=None,
        max_length=100,
    )
    size: str | None = Field(
        default=None,
        max_length=32,
    )
    quantity: int = Field(
        gt=0,
        le=1000,
        description="销售数量",
    )
    unit_price: Decimal = Field(
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="每双实际成交单价",
    )
    note: str | None = Field(
        default=None,
        max_length=500,
    )

    @field_validator(
        "local_sku",
        "brand",
        "article_number",
        "size",
    )
    @classmethod
    def normalize_business_value(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned_value = value.strip().upper()
        return cleaned_value or None

    @field_validator(
        "barcode",
        "note",
    )
    @classmethod
    def clean_optional_value(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned_value = value.strip()
        return cleaned_value or None

    @model_validator(mode="after")
    def require_sku_selector(self) -> Self:
        if not any(
            (
                self.local_sku,
                self.barcode,
                self.brand,
                self.article_number,
                self.size,
            )
        ):
            raise ValueError(
                "必须提供商品编码、条码、品牌、货号或尺码"
            )

        return self


class AgentToolResultRead(BaseModel):
    """一次 Agent 工具调用结果。"""

    name: str
    data: dict[str, Any]


class AgentActionRead(BaseModel):
    """需要用户人工确认的 Agent 业务操作。"""

    action_id: str
    action_type: AgentActionType
    status: AgentActionStatus
    preview: dict[str, Any]
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    expires_at: datetime
    confirmed_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    requires_confirmation: bool


class AgentChatData(BaseModel):
    """Agent 对话成功返回结构。"""

    reply: str
    tools_used: list[str] = Field(
        default_factory=list,
    )
    tool_results: list[AgentToolResultRead] = Field(
        default_factory=list,
    )
    pending_action: AgentActionRead | None = None
