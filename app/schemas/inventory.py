from datetime import datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

from app.models.inventory import StockMovementType


class StockInboundCreate(BaseModel):
    """商品入库请求。"""

    local_sku: str = Field(
        min_length=1,
        max_length=32,
        description="系统内部 SKU 编码",
    )

    quantity: int = Field(
        gt=0,
        description="本次入库数量，必须大于 0",
    )

    unit_cost: Decimal = Field(
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="本次入库的单件成本",
    )

    reference_no: str | None = Field(
        default=None,
        max_length=100,
        description="采购单号或外部参考编号",
    )

    note: str | None = Field(
        default=None,
        max_length=500,
        description="入库备注",
    )

    @field_validator("local_sku")
    @classmethod
    def normalize_local_sku(
        cls,
        value: str,
    ) -> str:
        return value.strip().upper()

    @field_validator(
        "reference_no",
        "note",
    )
    @classmethod
    def clean_optional_text(
        cls,
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        cleaned_value = value.strip()

        if not cleaned_value:
            return None

        return cleaned_value


class InventoryRead(BaseModel):
    """当前库存返回结构。"""

    local_sku: str
    barcode: str | None
    brand: str
    article_number: str
    size: str

    on_hand_qty: int
    reserved_qty: int
    available_qty: int

    avg_cost: Decimal
    inventory_value: Decimal

    updated_at: datetime | None


class StockMovementRead(BaseModel):
    """库存流水返回结构。"""

    movement_no: str
    local_sku: str
    movement_type: StockMovementType

    quantity_change: int
    unit_cost: Decimal

    before_qty: int
    after_qty: int

    before_avg_cost: Decimal
    after_avg_cost: Decimal

    reference_no: str | None
    note: str | None
    created_at: datetime