from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    DateTime,
    Enum,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SKUStatus(StrEnum):
    """SKU 状态。"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"


class SKU(Base):
    """SKU 主数据表。"""

    __tablename__ = "skus"

    __table_args__ = (
        UniqueConstraint(
            "brand",
            "article_number",
            "size",
            name="uq_skus_business_key",
        ),
        UniqueConstraint(
            "barcode",
            name="uq_skus_barcode",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    local_sku: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        nullable=False,
    )

    barcode: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    brand: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    article_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    size: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    status: Mapped[SKUStatus] = mapped_column(
        Enum(
            SKUStatus,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        nullable=False,
        default=SKUStatus.ACTIVE,
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