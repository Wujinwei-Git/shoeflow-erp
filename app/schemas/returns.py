from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from app.models.returns import ReturnType


class ReturnItemCreate(BaseModel):
    """退货商品请求。"""

    local_sku: str = Field(
        min_length=1,
        max_length=32,
    )

    quantity: int = Field(
        gt=0,
        description="本次退货数量",
    )

    @field_validator("local_sku")
    @classmethod
    def normalize_local_sku(
        cls,
        value: str,
    ) -> str:
        return value.strip().upper()


class ReturnCreate(BaseModel):
    """创建顾客退货请求。"""

    sale_no: str = Field(
        min_length=1,
        max_length=40,
    )

    items: list[ReturnItemCreate] = Field(
        min_length=1,
        max_length=100,
    )

    note: str | None = Field(
        default=None,
        max_length=500,
    )

    @field_validator("sale_no")
    @classmethod
    def normalize_sale_no(
        cls,
        value: str,
    ) -> str:
        return value.strip().upper()

    @field_validator("note")
    @classmethod
    def clean_note(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned_value = value.strip()

        return cleaned_value or None

    @model_validator(mode="after")
    def validate_unique_skus(self) -> Self:
        local_skus = [
            item.local_sku
            for item in self.items
        ]

        if len(local_skus) != len(set(local_skus)):
            raise ValueError(
                "同一退货单中不能重复填写相同的 SKU"
            )

        return self


class SaleReverseCreate(BaseModel):
    """销售冲销请求。"""

    note: str | None = Field(
        default=None,
        max_length=500,
    )

    @field_validator("note")
    @classmethod
    def clean_note(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned_value = value.strip()

        return cleaned_value or None


class ReturnItemRead(BaseModel):
    """退货明细返回结构。"""

    local_sku: str
    barcode: str | None
    brand: str
    article_number: str
    size: str

    quantity: int
    unit_price: Decimal
    unit_cost: Decimal

    line_amount: Decimal
    line_cost: Decimal
    line_profit_reversal: Decimal


class ReturnRead(BaseModel):
    """完整退货单返回结构。"""

    return_no: str
    sale_no: str
    return_type: ReturnType

    total_amount: Decimal
    total_cost: Decimal
    gross_profit_reversal: Decimal

    note: str | None
    returned_at: datetime

    items: list[ReturnItemRead]


class ReturnSummaryRead(BaseModel):
    """退货记录列表结构。"""

    return_no: str
    sale_no: str
    return_type: ReturnType

    total_amount: Decimal
    total_cost: Decimal
    gross_profit_reversal: Decimal

    returned_at: datetime