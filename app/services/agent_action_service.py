from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi import status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.agent import (
    AgentAction,
    AgentActionStatus,
    AgentActionType,
)
from app.models.inventory import Inventory
from app.models.sales import SalesOrder
from app.models.sku import SKU, SKUStatus
from app.models.user import User
from app.schemas.agent import (
    AgentActionRead,
    AgentQueryArguments,
    AgentSalePreviewArguments,
)
from app.schemas.sales import SaleCreate, SaleRead
from app.services.agent_tools import apply_sku_filters
from app.services.inventory_service import quantize_money
from app.services.sales_service import (
    build_sale_data,
    create_sale,
)


SALE_PREVIEW_TOOL_DEFINITION: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "preview_sale",
        "description": (
            "为销售或销售出库生成待确认预览，不会立即扣减库存。"
            "用户明确给出商品、数量和每双实际成交单价后使用。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
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
                    "description": "鞋款货号",
                },
                "size": {
                    "type": "string",
                    "description": "鞋码，例如 42 或 EUR 42",
                },
                "quantity": {
                    "type": "integer",
                    "description": "销售数量，单位为双",
                    "minimum": 1,
                    "maximum": 1000,
                },
                "unit_price": {
                    "type": "number",
                    "description": "每双实际成交单价，单位为元",
                    "minimum": 0,
                },
                "note": {
                    "type": "string",
                    "description": "可选销售备注",
                },
            },
            "required": [
                "quantity",
                "unit_price",
            ],
            "additionalProperties": False,
        },
    },
}


def utc_now() -> datetime:
    """返回适合 MySQL DATETIME 与 SQLite 的无时区 UTC 时间。"""

    return datetime.now(timezone.utc).replace(
        tzinfo=None
    )


def tool_error(
    code: str,
    message: str,
    *,
    details: Any = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": jsonable_encoder(details),
        },
    }


def serialize_agent_action(
    action: AgentAction,
) -> dict[str, Any]:
    """构造稳定、适合移动端渲染的待确认操作数据。"""

    action_data = AgentActionRead(
        action_id=action.id,
        action_type=action.action_type,
        status=action.status,
        preview=action.preview_json,
        result=action.result_json,
        error=action.error_json,
        expires_at=action.expires_at,
        confirmed_at=action.confirmed_at,
        cancelled_at=action.cancelled_at,
        created_at=action.created_at,
        requires_confirmation=(
            action.status == AgentActionStatus.PENDING
            and action.expires_at > utc_now()
        ),
    )

    return action_data.model_dump(mode="json")


def _query_sale_candidates(
    db: Session,
    arguments: AgentSalePreviewArguments,
) -> list[tuple[SKU, Inventory | None]]:
    query_arguments = AgentQueryArguments(
        local_sku=arguments.local_sku,
        barcode=arguments.barcode,
        brand=arguments.brand,
        article_number=arguments.article_number,
        size=arguments.size,
        limit=3,
    )

    statement = (
        select(SKU, Inventory)
        .outerjoin(
            Inventory,
            Inventory.sku_id == SKU.id,
        )
    )
    statement = apply_sku_filters(
        statement,
        query_arguments,
    )
    statement = statement.order_by(
        SKU.article_number,
        SKU.size,
    ).limit(3)

    return list(db.execute(statement).all())


def _candidate_summary(sku: SKU) -> dict[str, Any]:
    return {
        "local_sku": sku.local_sku,
        "barcode": sku.barcode,
        "brand": sku.brand,
        "article_number": sku.article_number,
        "size": sku.size,
        "status": sku.status.value,
    }


def create_sale_preview_action(
    db: Session,
    *,
    current_user: User,
    request_text: str,
    arguments: AgentSalePreviewArguments,
) -> dict[str, Any]:
    """校验销售条件并创建待确认操作，绝不在此处扣库存。"""

    candidates = _query_sale_candidates(
        db=db,
        arguments=arguments,
    )

    if not candidates:
        return tool_error(
            "SKU_NOT_FOUND",
            "没有找到匹配的商品，请核对货号、尺码或条码",
        )

    if len(candidates) > 1:
        return tool_error(
            "SKU_AMBIGUOUS",
            "匹配到多个商品，请补充品牌、货号、尺码或条码",
            details={
                "candidates": [
                    _candidate_summary(sku)
                    for sku, _ in candidates
                ],
            },
        )

    sku, inventory = candidates[0]

    if sku.status != SKUStatus.ACTIVE:
        return tool_error(
            "SKU_NOT_ACTIVE",
            "只有正常启用的 SKU 才能销售",
            details=_candidate_summary(sku),
        )

    if inventory is None:
        on_hand_qty = 0
        reserved_qty = 0
        avg_cost = Decimal("0.00")
    else:
        on_hand_qty = inventory.on_hand_qty
        reserved_qty = inventory.reserved_qty
        avg_cost = quantize_money(
            inventory.avg_cost
        )

    available_qty = on_hand_qty - reserved_qty

    if available_qty < arguments.quantity:
        return tool_error(
            "INSUFFICIENT_STOCK",
            "可用库存不足，未生成待确认销售单",
            details={
                "local_sku": sku.local_sku,
                "available_qty": available_qty,
                "requested_qty": arguments.quantity,
            },
        )

    unit_price = quantize_money(
        arguments.unit_price
    )
    line_amount = quantize_money(
        unit_price * Decimal(arguments.quantity)
    )
    line_cost = quantize_money(
        avg_cost * Decimal(arguments.quantity)
    )
    line_profit = quantize_money(
        line_amount - line_cost
    )

    warnings: list[str] = []

    if avg_cost == Decimal("0.00"):
        warnings.append(
            "当前平均成本为 0.00 元，请确认成本数据是否完整"
        )

    if line_profit < Decimal("0.00"):
        warnings.append(
            "本次预计毛利润为负数，请确认成交价格"
        )

    sale_payload = SaleCreate(
        items=[
            {
                "local_sku": sku.local_sku,
                "quantity": arguments.quantity,
                "unit_price": unit_price,
            }
        ],
        note=arguments.note,
    )

    payload_json = {
        "sale": sale_payload.model_dump(mode="json"),
        "snapshot": {
            "items": [
                {
                    "local_sku": sku.local_sku,
                    "on_hand_qty": on_hand_qty,
                    "reserved_qty": reserved_qty,
                    "avg_cost": str(avg_cost),
                }
            ]
        },
    }

    preview_json = {
        "title": "销售出库确认",
        "action_type": AgentActionType.SALE.value,
        "items": [
            {
                "local_sku": sku.local_sku,
                "barcode": sku.barcode,
                "brand": sku.brand,
                "article_number": sku.article_number,
                "size": sku.size,
                "quantity": arguments.quantity,
                "on_hand_qty": on_hand_qty,
                "reserved_qty": reserved_qty,
                "available_qty": available_qty,
                "after_on_hand_qty": (
                    on_hand_qty - arguments.quantity
                ),
                "unit_price": str(unit_price),
                "unit_cost": str(avg_cost),
                "line_amount": str(line_amount),
                "line_cost": str(line_cost),
                "line_profit": str(line_profit),
            }
        ],
        "total_quantity": arguments.quantity,
        "total_amount": str(line_amount),
        "total_cost": str(line_cost),
        "gross_profit": str(line_profit),
        "note": arguments.note,
        "warnings": warnings,
    }

    action = AgentAction(
        id=str(uuid4()),
        user_id=current_user.id,
        action_type=AgentActionType.SALE,
        status=AgentActionStatus.PENDING,
        request_text=request_text,
        payload_json=payload_json,
        preview_json=preview_json,
        expires_at=(
            utc_now()
            + timedelta(
                minutes=(
                    settings.agent_action_expire_minutes
                )
            )
        ),
    )

    db.add(action)
    db.commit()
    db.refresh(action)

    return {
        "ok": True,
        "data": {
            "pending_action": serialize_agent_action(
                action
            ),
        },
    }


def execute_sale_preview_tool(
    db: Session,
    *,
    current_user: User,
    request_text: str,
    raw_arguments: Any,
) -> dict[str, Any]:
    try:
        arguments = AgentSalePreviewArguments.model_validate(
            raw_arguments
        )
    except ValidationError:
        return tool_error(
            "INVALID_TOOL_ARGUMENTS",
            "销售预览参数不完整，请确认商品、数量和每双成交价",
        )

    return create_sale_preview_action(
        db=db,
        current_user=current_user,
        request_text=request_text,
        arguments=arguments,
    )


def _get_owned_action(
    db: Session,
    *,
    action_id: str,
    user_id: int,
    lock_for_update: bool = False,
) -> AgentAction:
    statement = select(AgentAction).where(
        AgentAction.id == action_id,
        AgentAction.user_id == user_id,
    )

    if lock_for_update:
        statement = statement.with_for_update()

    action = db.scalar(statement)

    if action is None:
        raise AppException(
            message="待确认操作不存在或不属于当前账号",
            code="AGENT_ACTION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return action


def _mark_action_failed(
    db: Session,
    *,
    action_id: str,
    user_id: int,
    code: str,
    message: str,
    details: Any = None,
) -> None:
    """执行失败后单独记录状态，不覆盖原始业务异常。"""

    try:
        action = _get_owned_action(
            db=db,
            action_id=action_id,
            user_id=user_id,
            lock_for_update=True,
        )

        if action.status == AgentActionStatus.PENDING:
            action.status = AgentActionStatus.FAILED
            action.error_json = {
                "code": code,
                "message": message,
                "details": jsonable_encoder(details),
            }
            db.commit()
    except Exception:
        db.rollback()


def _raise_for_non_pending_action(
    action: AgentAction,
) -> None:
    if action.status == AgentActionStatus.CANCELLED:
        raise AppException(
            message="该操作已经取消，不能再确认",
            code="AGENT_ACTION_CANCELLED",
            status_code=status.HTTP_409_CONFLICT,
        )

    if action.status == AgentActionStatus.EXPIRED:
        raise AppException(
            message="该操作已经过期，请重新生成预览",
            code="AGENT_ACTION_EXPIRED",
            status_code=status.HTTP_409_CONFLICT,
        )

    if action.status == AgentActionStatus.FAILED:
        raise AppException(
            message="该操作执行失败，请重新生成预览",
            code="AGENT_ACTION_FAILED",
            status_code=status.HTTP_409_CONFLICT,
            details=action.error_json,
        )

    if action.status != AgentActionStatus.PENDING:
        raise AppException(
            message="该操作当前状态不能确认",
            code="AGENT_ACTION_INVALID_STATUS",
            status_code=status.HTTP_409_CONFLICT,
        )


def _expire_action_if_needed(
    db: Session,
    action: AgentAction,
) -> bool:
    if (
        action.status == AgentActionStatus.PENDING
        and action.expires_at <= utc_now()
    ):
        action.status = AgentActionStatus.EXPIRED
        db.commit()
        db.refresh(action)
        return True

    return False


def _load_sale_payload_and_lock_snapshot(
    db: Session,
    action: AgentAction,
) -> SaleCreate:
    payload_json = action.payload_json

    if not isinstance(payload_json, dict):
        raise AppException(
            message="待确认销售数据无效，请重新生成预览",
            code="AGENT_ACTION_PAYLOAD_INVALID",
            status_code=status.HTTP_409_CONFLICT,
        )

    try:
        sale_payload = SaleCreate.model_validate(
            payload_json.get("sale")
        )
    except ValidationError as exc:
        raise AppException(
            message="待确认销售数据无效，请重新生成预览",
            code="AGENT_ACTION_PAYLOAD_INVALID",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc

    snapshot = payload_json.get("snapshot")
    snapshot_items = (
        snapshot.get("items")
        if isinstance(snapshot, dict)
        else None
    )

    if not isinstance(snapshot_items, list):
        raise AppException(
            message="销售预览快照无效，请重新生成预览",
            code="AGENT_ACTION_PAYLOAD_INVALID",
            status_code=status.HTTP_409_CONFLICT,
        )

    snapshot_by_sku = {
        item.get("local_sku"): item
        for item in snapshot_items
        if isinstance(item, dict)
        and isinstance(item.get("local_sku"), str)
    }

    for sale_item in sale_payload.items:
        expected = snapshot_by_sku.get(
            sale_item.local_sku
        )

        if expected is None:
            raise AppException(
                message="销售预览快照无效，请重新生成预览",
                code="AGENT_ACTION_PAYLOAD_INVALID",
                status_code=status.HTTP_409_CONFLICT,
            )

        statement = (
            select(SKU, Inventory)
            .outerjoin(
                Inventory,
                Inventory.sku_id == SKU.id,
            )
            .where(
                SKU.local_sku == sale_item.local_sku
            )
            .with_for_update()
        )
        current_row = db.execute(statement).first()

        if current_row is None:
            raise AppException(
                message="商品状态已经变化，请重新生成销售预览",
                code="AGENT_PREVIEW_STALE",
                status_code=status.HTTP_409_CONFLICT,
            )

        _, inventory = current_row

        current_on_hand = (
            inventory.on_hand_qty
            if inventory is not None
            else 0
        )
        current_reserved = (
            inventory.reserved_qty
            if inventory is not None
            else 0
        )
        current_avg_cost = quantize_money(
            inventory.avg_cost
            if inventory is not None
            else Decimal("0.00")
        )

        try:
            expected_on_hand = int(
                expected["on_hand_qty"]
            )
            expected_reserved = int(
                expected["reserved_qty"]
            )
            expected_avg_cost = quantize_money(
                Decimal(str(expected["avg_cost"]))
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AppException(
                message="销售预览快照无效，请重新生成预览",
                code="AGENT_ACTION_PAYLOAD_INVALID",
                status_code=status.HTTP_409_CONFLICT,
            ) from exc

        if (
            current_on_hand != expected_on_hand
            or current_reserved != expected_reserved
            or current_avg_cost != expected_avg_cost
        ):
            raise AppException(
                message="库存或成本已变化，请重新生成销售预览",
                code="AGENT_PREVIEW_STALE",
                status_code=status.HTTP_409_CONFLICT,
                details={
                    "local_sku": sale_item.local_sku,
                    "preview": {
                        "on_hand_qty": expected_on_hand,
                        "reserved_qty": expected_reserved,
                        "avg_cost": str(
                            expected_avg_cost
                        ),
                    },
                    "current": {
                        "on_hand_qty": current_on_hand,
                        "reserved_qty": current_reserved,
                        "avg_cost": str(current_avg_cost),
                    },
                },
            )

    return sale_payload


def confirm_agent_action(
    db: Session,
    *,
    action_id: str,
    current_user: User,
) -> tuple[AgentAction, bool]:
    """原子确认操作；重复确认返回原结果，不重复扣库存。"""

    action = _get_owned_action(
        db=db,
        action_id=action_id,
        user_id=current_user.id,
        lock_for_update=True,
    )

    if action.status == AgentActionStatus.CONFIRMED:
        return action, False

    _raise_for_non_pending_action(action)

    if _expire_action_if_needed(db, action):
        raise AppException(
            message="该操作已经过期，请重新生成预览",
            code="AGENT_ACTION_EXPIRED",
            status_code=status.HTTP_409_CONFLICT,
        )

    if action.action_type != AgentActionType.SALE:
        raise AppException(
            message="暂不支持确认该类操作",
            code="AGENT_ACTION_TYPE_NOT_SUPPORTED",
            status_code=status.HTTP_409_CONFLICT,
        )

    try:
        sale_payload = (
            _load_sale_payload_and_lock_snapshot(
                db=db,
                action=action,
            )
        )
        sales_order = create_sale(
            db=db,
            payload=sale_payload,
            commit=False,
        )
        sale_data = build_sale_data(
            db=db,
            sales_order=sales_order,
        )
        serialized_sale = (
            SaleRead
            .model_validate(sale_data)
            .model_dump(mode="json")
        )

        action.status = AgentActionStatus.CONFIRMED
        action.sales_order_id = sales_order.id
        action.result_json = {
            "sale": serialized_sale,
        }
        action.confirmed_at = utc_now()

        db.commit()
        db.refresh(action)

        return action, True

    except AppException as exc:
        db.rollback()
        _mark_action_failed(
            db=db,
            action_id=action_id,
            user_id=current_user.id,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )
        raise

    except Exception:
        db.rollback()
        _mark_action_failed(
            db=db,
            action_id=action_id,
            user_id=current_user.id,
            code="AGENT_ACTION_EXECUTION_FAILED",
            message="待确认操作执行失败",
        )
        raise


def cancel_agent_action(
    db: Session,
    *,
    action_id: str,
    current_user: User,
) -> tuple[AgentAction, bool]:
    """取消尚未执行的 Agent 操作。"""

    action = _get_owned_action(
        db=db,
        action_id=action_id,
        user_id=current_user.id,
        lock_for_update=True,
    )

    if action.status == AgentActionStatus.CANCELLED:
        return action, False

    if action.status == AgentActionStatus.CONFIRMED:
        raise AppException(
            message="销售已经确认，不能通过取消操作撤销",
            code="AGENT_ACTION_ALREADY_CONFIRMED",
            status_code=status.HTTP_409_CONFLICT,
        )

    _raise_for_non_pending_action(action)

    if _expire_action_if_needed(db, action):
        raise AppException(
            message="该操作已经过期",
            code="AGENT_ACTION_EXPIRED",
            status_code=status.HTTP_409_CONFLICT,
        )

    action.status = AgentActionStatus.CANCELLED
    action.cancelled_at = utc_now()
    db.commit()
    db.refresh(action)

    return action, True


def get_agent_action(
    db: Session,
    *,
    action_id: str,
    current_user: User,
) -> AgentAction:
    """查询当前账号自己的 Agent 操作。"""

    action = _get_owned_action(
        db=db,
        action_id=action_id,
        user_id=current_user.id,
    )
    _expire_action_if_needed(db, action)

    return action
