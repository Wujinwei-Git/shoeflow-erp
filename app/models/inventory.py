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


class StockMovementType(StrEnum):
    """库存流水类型。"""

    INBOUND = "inbound"
    SALE = "sale"
    RETURN = "return"
    ADJUSTMENT = "adjustment"
    REVERSAL = "reversal"


class Inventory(Base):
    """SKU 当前库存汇总表。"""

    __tablename__ = "inventories"

    __table_args__ = (
        UniqueConstraint(
            "sku_id",
            name="uq_inventories_sku_id",
        ),
        CheckConstraint(
            "on_hand_qty >= 0",
            name="on_hand_qty_non_negative",
        ),
        CheckConstraint(
            "reserved_qty >= 0",
            name="reserved_qty_non_negative",
        ),
        CheckConstraint(
            "reserved_qty <= on_hand_qty",
            name="reserved_qty_not_exceed_on_hand",
        ),
        CheckConstraint(
            "avg_cost >= 0",
            name="avg_cost_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    sku_id: Mapped[int] = mapped_column(
        ForeignKey(
            "skus.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    on_hand_qty: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    reserved_qty: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    avg_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class StockMovement(Base):
    """不可直接修改的库存流水表。"""

    __tablename__ = "stock_movements"

    __table_args__ = (
        UniqueConstraint(
            "movement_no",
            name="uq_stock_movements_movement_no",
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
            "unit_cost >= 0",
            name="unit_cost_non_negative",
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

    movement_no: Mapped[str] = mapped_column(
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

    movement_type: Mapped[StockMovementType] = mapped_column(
        Enum(
            StockMovementType,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        nullable=False,
    )

    quantity_change: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_cost: Mapped[Decimal] = mapped_column(
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

    reference_no: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
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