"""导入所有 SQLAlchemy 模型，供 Alembic 发现。"""

from app.models.agent import (
    AgentAction,
    AgentActionStatus,
    AgentActionType,
)
from app.models.corrections import (
    CorrectionReason,
    InventoryCorrection,
)
from app.models.inventory import (
    Inventory,
    StockMovement,
    StockMovementType,
)
from app.models.returns import (
    ReturnItem,
    ReturnOrder,
    ReturnType,
)
from app.models.sales import (
    SalesItem,
    SalesOrder,
    SaleStatus,
)
from app.models.sku import SKU, SKUStatus
from app.models.user import User, UserRole

__all__ = [
    "AgentAction",
    "AgentActionStatus",
    "AgentActionType",
    "SKU",
    "SKUStatus",
    "Inventory",
    "StockMovement",
    "StockMovementType",
    "SalesOrder",
    "SalesItem",
    "SaleStatus",
    "ReturnOrder",
    "ReturnItem",
    "ReturnType",
    "InventoryCorrection",
    "CorrectionReason",
    "User",
    "UserRole",
]
