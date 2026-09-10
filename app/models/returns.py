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


class ReturnType(StrEnum):
    """退货业务类型。"""

    CUSTOMER_RETURN = "customer_return"
    SALE_REVERSAL = "sale_reversal"


class ReturnOrder(Base):
    """退货或冲销主表。"""

    __tablename__ = "return_orders"

    __table_args__ = (
        UniqueConstraint(
            "return_no",
            name="uq_return_orders_return_no",
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

    return_no: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    sales_order_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sales_orders.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    return_type: Mapped[ReturnType] = mapped_column(
        Enum(
            ReturnType,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        nullable=False,
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

    gross_profit_reversal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    note: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    returned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ReturnItem(Base):
    """退货或冲销明细表。"""

    __tablename__ = "return_items"

    __table_args__ = (
        UniqueConstraint(
            "return_order_id",
            "sales_item_id",
            name="uq_return_items_order_sales_item",
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

    return_order_id: Mapped[int] = mapped_column(
        ForeignKey(
            "return_orders.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    sales_item_id: Mapped[int] = mapped_column(
        ForeignKey(
            "sales_items.id",
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

    line_profit_reversal: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )