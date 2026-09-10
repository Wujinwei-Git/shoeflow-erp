from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentActionType(StrEnum):
    """Agent 当前支持的待确认业务类型。"""

    SALE = "sale"


class AgentActionStatus(StrEnum):
    """Agent 待确认操作状态。"""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


class AgentAction(Base):
    """模型生成、但必须由用户确认后才能执行的业务操作。"""

    __tablename__ = "agent_actions"

    __table_args__ = (
        UniqueConstraint(
            "sales_order_id",
            name="uq_agent_actions_sales_order_id",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    sales_order_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "sales_orders.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    action_type: Mapped[AgentActionType] = mapped_column(
        Enum(
            AgentActionType,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        nullable=False,
    )

    status: Mapped[AgentActionStatus] = mapped_column(
        Enum(
            AgentActionStatus,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
        ),
        nullable=False,
        index=True,
    )

    request_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    preview_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    result_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    error_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
    )

    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
