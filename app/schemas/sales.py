from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from app.models.sales import SaleStatus


class SaleItemCreate(BaseModel):
    """销售商品请求。"""

    local_sku: str = Field(
        min_length=1,
        max_length=32,
        description="系统内部 SKU 编码",
    )

    quantity: int = Field(
        gt=0,
        description="销售数量，必须大于 0",
    )

    unit_price: Decimal = Field(
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="实际销售单价",
    )

    @field_validator("local_sku")
    @classmethod
    def normalize_local_sku(
        cls,
        value: str,
    ) -> str:
        return value.strip().upper()


class SaleCreate(BaseModel):
    """创建销售单请求。"""

    items: list[SaleItemCreate] = Field(
        min_length=1,
        max_length=100,
    )

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

    @model_validator(mode="after")
    def validate_unique_skus(self) -> Self:
        local_skus = [
            item.local_sku
            for item in self.items
        ]

        if len(local_skus) != len(set(local_skus)):
            raise ValueError(
                "同一销售单中不能重复填写相同的 SKU"
            )

        return self


class SaleItemRead(BaseModel):
    """销售明细返回结构。"""

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
    line_profit: Decimal


class SaleRead(BaseModel):
    """完整销售单返回结构。"""

    sale_no: str
    status: SaleStatus

    total_amount: Decimal
    total_cost: Decimal
    gross_profit: Decimal

    note: str | None
    sold_at: datetime

    items: list[SaleItemRead]


class SaleSummaryRead(BaseModel):
    """销售记录列表返回结构。"""

    sale_no: str
    status: SaleStatus

    total_amount: Decimal
    total_cost: Decimal
    gross_profit: Decimal

    sold_at: datetime