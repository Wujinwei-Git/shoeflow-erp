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


class SaleStatus(StrEnum):
    """销售单状态。"""

    COMPLETED = "completed"
    PARTIALLY_RETURNED = "partially_returned"
    RETURNED = "returned"
    REVERSED = "reversed"


class SalesOrder(Base):
    """销售单主表。"""

    __tablename__ = "sales_orders"

    __table_args__ = (
        UniqueConstraint(
            "sale_no",
            name="uq_sales_orders_sale_no",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="total_amount_non_negative",
        ),
        CheckConstraint(
            "total_cost >= 0",
            name="total_cost_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    sale_no: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    status: Mapped[SaleStatus] = mapped_column(
        Enum(
            SaleStatus,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        nullable=False,
        default=SaleStatus.COMPLETED,
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    gross_profit: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    sold_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class SalesItem(Base):
    """销售单明细表。"""

    __tablename__ = "sales_items"

    __table_args__ = (
        UniqueConstraint(
            "sales_order_id",
            "sku_id",
            name="uq_sales_items_order_sku",
        ),
        CheckConstraint(
            "quantity > 0",
            name="quantity_positive",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="unit_price_non_negative",
        ),
        CheckConstraint(
            "unit_cost >= 0",
            name="unit_cost_non_negative",
        ),
        CheckConstraint(
            "line_amount >= 0",
            name="line_amount_non_negative",
        ),
        CheckConstraint(
            "line_cost >= 0",
            name="line_cost_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    sales_order_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sales_orders.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    sku_id: Mapped[int] = mapped_column(
        ForeignKey(
            "skus.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    line_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    line_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    line_profit: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )