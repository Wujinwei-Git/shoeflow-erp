from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.models.sku import SKU
from app.schemas.agent import AgentQueryArguments
from app.schemas.inventory import InventoryRead
from app.schemas.sku import SKURead
from app.services.inventory_service import (
    build_inventory_data,
)


QUERY_PROPERTIES: dict[str, Any] = {
    "local_sku": {
        "type": "string",
        "description": "系统内部 SKU 编码",
    },
    "barcode": {
        "type": "string",
        "description": "鞋盒条码",
    },
    "brand": {
        "type": "string",
        "description": "品牌，例如 NIKE",
    },
    "article_number": {
        "type": "string",
        "description": "鞋款货号，例如 DD1391-100",
    },
    "size": {
        "type": "string",
        "description": "鞋码，例如 42 或 EUR 42",
    },
    "limit": {
        "type": "integer",
        "description": "最多返回多少条，默认 20，最大 50",
        "minimum": 1,
        "maximum": 50,
    },
}


READ_ONLY_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_skus",
            "description": (
                "按内部 SKU、条码、品牌、货号或尺码查询 SKU "
                "档案。用户询问商品是否存在、商品编码或状态时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": QUERY_PROPERTIES,
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_inventory",
            "description": (
                "按内部 SKU、条码、品牌、货号或尺码查询实时库存、"
                "可用库存、平均成本和库存金额。询问库存时必须使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": QUERY_PROPERTIES,
                "additionalProperties": False,
            },
        },
    },
]


def _size_candidates(size: str) -> set[str]:
    normalized_size = size.strip().upper()

    if normalized_size.startswith("EUR "):
        numeric_part = normalized_size[4:].strip()
    else:
        numeric_part = normalized_size

    return {
        normalized_size,
        numeric_part,
        f"EUR {numeric_part}",
    }


def apply_sku_filters(
    statement: Any,
    arguments: AgentQueryArguments,
) -> Any:
    if arguments.local_sku:
        statement = statement.where(
            SKU.local_sku == arguments.local_sku
        )

    if arguments.barcode:
        statement = statement.where(
            SKU.barcode == arguments.barcode
        )

    if arguments.brand:
        statement = statement.where(
            SKU.brand == arguments.brand
        )

    if arguments.article_number:
        statement = statement.where(
            SKU.article_number
            == arguments.article_number
        )

    if arguments.size:
        candidates = _size_candidates(arguments.size)
        statement = statement.where(
            or_(
                *[
                    SKU.size == candidate
                    for candidate in candidates
                ]
            )
        )

    return statement


def search_skus(
    db: Session,
    arguments: AgentQueryArguments,
) -> dict[str, Any]:
    """只读查询 SKU 档案。"""

    statement = select(SKU)
    statement = apply_sku_filters(
        statement,
        arguments,
    )
    statement = statement.order_by(
        SKU.article_number,
        SKU.size,
    ).limit(arguments.limit)

    items = [
        SKURead
        .model_validate(sku)
        .model_dump(mode="json")
        for sku in db.scalars(statement).all()
    ]

    return {
        "count": len(items),
        "items": items,
    }


def query_inventory(
    db: Session,
    arguments: AgentQueryArguments,
) -> dict[str, Any]:
    """只读查询 SKU 及其实时库存。"""

    statement = (
        select(SKU, Inventory)
        .outerjoin(
            Inventory,
            Inventory.sku_id == SKU.id,
        )
    )
    statement = apply_sku_filters(
        statement,
        arguments,
    )
    statement = statement.order_by(
        SKU.article_number,
        SKU.size,
    ).limit(arguments.limit)

    items: list[dict[str, Any]] = []

    for sku, inventory in db.execute(statement).all():
        if inventory is None:
            inventory_data = {
                "local_sku": sku.local_sku,
                "barcode": sku.barcode,
                "brand": sku.brand,
                "article_number": sku.article_number,
                "size": sku.size,
                "on_hand_qty": 0,
                "reserved_qty": 0,
                "available_qty": 0,
                "avg_cost": Decimal("0.00"),
                "inventory_value": Decimal("0.00"),
                "updated_at": None,
            }
        else:
            inventory_data = build_inventory_data(
                sku=sku,
                inventory=inventory,
            )

        items.append(
            InventoryRead
            .model_validate(inventory_data)
            .model_dump(mode="json")
        )

    return {
        "count": len(items),
        "items": items,
    }


def execute_read_only_tool(
    db: Session,
    *,
    name: str,
    raw_arguments: Any,
) -> dict[str, Any]:
    """仅执行显式列入白名单的只读工具。"""

    try:
        arguments = AgentQueryArguments.model_validate(
            raw_arguments
        )
    except ValidationError:
        return {
            "ok": False,
            "error": {
                "code": "INVALID_TOOL_ARGUMENTS",
                "message": "查询参数无效，请重新确认条件",
            },
        }

    if name == "search_skus":
        data = search_skus(
            db=db,
            arguments=arguments,
        )
    elif name == "query_inventory":
        data = query_inventory(
            db=db,
            arguments=arguments,
        )
    else:
        return {
            "ok": False,
            "error": {
                "code": "TOOL_NOT_ALLOWED",
                "message": "该工具未获授权",
            },
        }

    return {
        "ok": True,
        "data": data,
    }
