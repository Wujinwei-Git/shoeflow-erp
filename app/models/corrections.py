from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CorrectionReason(StrEnum):
    """库存校正原因。"""

    DUPLICATE_SCAN = "duplicate_scan"
    MISSED_SCAN = "missed_scan"
    WRONG_SKU = "wrong_sku"
    DAMAGE = "damage"
    OTHER = "other"


class InventoryCorrection(Base):
    """库存数量校正记录。"""

    __tablename__ = "inventory_corrections"

    __table_args__ = (
        UniqueConstraint(
            "correction_no",
            name="uq_inventory_corrections_correction_no",
        ),
        CheckConstraint(
            "quantity_change <> 0",
            name="quantity_change_not_zero",
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="unit_cost_non_negative",
        ),
        CheckConstraint(
            "before_qty >= 0",
            name="before_qty_non_negative",
        ),
        CheckConstraint(
            "after_qty >= 0",
            name="after_qty_non_negative",
        ),
        CheckConstraint(
            "before_avg_cost >= 0",
            name="before_avg_cost_non_negative",
        ),
        CheckConstraint(
            "after_avg_cost >= 0",
            name="after_avg_cost_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    correction_no: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    sku_id: Mapped[int] = mapped_column(
        ForeignKey(
            "skus.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    quantity_change: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    inventory_value_change: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    before_qty: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    after_qty: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    before_avg_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    after_avg_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    reason: Mapped[CorrectionReason] = mapped_column(
        Enum(
            CorrectionReason,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        nullable=False,
    )

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )