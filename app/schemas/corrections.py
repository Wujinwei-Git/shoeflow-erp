from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from app.models.corrections import CorrectionReason


class InventoryCorrectionCreate(BaseModel):
    """创建库存数量校正请求。"""

    local_sku: str = Field(
        min_length=1,
        max_length=32,
    )

    quantity_change: int = Field(
        description="正数增加库存，负数减少库存",
    )

    unit_cost: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="增加库存时可填写本双成本",
    )

    reason: CorrectionReason

    note: str | None = Field(
        default=None,
        max_length=500,
    )

    @field_validator("local_sku")
    @classmethod
    def normalize_local_sku(
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
    def validate_correction(self) -> Self:
        if self.quantity_change == 0:
            raise ValueError(
                "库存变化数量不能为0"
            )

        if (
            self.quantity_change < 0
            and self.unit_cost is not None
        ):
            raise ValueError(
                "减少库存时不需要填写单位成本"
            )

        return self


class InventoryCorrectionRead(BaseModel):
    """库存校正返回结构。"""

    correction_no: str

    local_sku: str
    barcode: str | None
    brand: str
    article_number: str
    size: str

    quantity_change: int
    unit_cost: Decimal
    inventory_value_change: Decimal

    before_qty: int
    after_qty: int

    before_avg_cost: Decimal
    after_avg_cost: Decimal

    reason: CorrectionReason
    note: str | None
    created_at: datetime