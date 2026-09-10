from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from app.models.sku import SKUStatus


def clean_required_value(value: str) -> str:
    """清理并统一品牌、货号和尺码。"""

    cleaned_value = value.strip()

    if not cleaned_value:
        raise ValueError("不能为空")

    return cleaned_value.upper()


class SKUCreate(BaseModel):
    """创建 SKU 请求。"""

    barcode: str | None = Field(
        default=None,
        max_length=64,
        description="鞋盒条码，允许为空；填写后必须唯一",
    )

    brand: str = Field(
        min_length=1,
        max_length=100,
        description="品牌",
    )

    article_number: str = Field(
        min_length=1,
        max_length=100,
        description="货号",
    )

    size: str = Field(
        min_length=1,
        max_length=32,
        description="鞋码",
    )

    status: SKUStatus = SKUStatus.ACTIVE

    @field_validator(
        "brand",
        "article_number",
        "size",
    )
    @classmethod
    def normalize_business_fields(
        cls,
        value: str,
    ) -> str:
        return clean_required_value(value)

    @field_validator("barcode")
    @classmethod
    def normalize_barcode(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned_value = value.strip()

        if not cleaned_value:
            return None

        return cleaned_value


class SKUStatusUpdate(BaseModel):
    """修改 SKU 状态请求。"""

    status: SKUStatus


class SKURead(BaseModel):
    """SKU 返回结构。"""

    model_config = ConfigDict(
        from_attributes=True,
    )

    local_sku: str
    barcode: str | None
    brand: str
    article_number: str
    size: str
    status: SKUStatus
    created_at: datetime
    updated_at: datetime