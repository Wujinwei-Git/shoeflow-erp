"""create agent actions table

Revision ID: 7f4a2c9d1e30
Revises: 9dac65d043ea
Create Date: 2026-09-08 17:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7f4a2c9d1e30"
down_revision: Union[str, Sequence[str], None] = (
    "9dac65d043ea"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_actions",
        sa.Column(
            "id",
            sa.String(length=36),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "sales_order_id",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "action_type",
            sa.Enum(
                "sale",
                name="agentactiontype",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "confirmed",
                "cancelled",
                "expired",
                "failed",
                name="agentactionstatus",
            ),
            nullable=False,
        ),
        sa.Column(
            "request_text",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "payload_json",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "preview_json",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "result_json",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "error_json",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column(
            "confirmed_at",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "cancelled_at",
            sa.DateTime(),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["sales_order_id"],
            ["sales_orders.id"],
            name=op.f(
                "fk_agent_actions_sales_order_id_sales_orders"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f(
                "fk_agent_actions_user_id_users"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_agent_actions"),
        ),
        sa.UniqueConstraint(
            "sales_order_id",
            name="uq_agent_actions_sales_order_id",
        ),
    )
    op.create_index(
        op.f("ix_agent_actions_expires_at"),
        "agent_actions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_actions_status"),
        "agent_actions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_actions_user_id"),
        "agent_actions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_agent_actions_user_id"),
        table_name="agent_actions",
    )
    op.drop_index(
        op.f("ix_agent_actions_status"),
        table_name="agent_actions",
    )
    op.drop_index(
        op.f("ix_agent_actions_expires_at"),
        table_name="agent_actions",
    )
    op.drop_table("agent_actions")
