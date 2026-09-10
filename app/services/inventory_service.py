from decimal import (
    Decimal,
    ROUND_HALF_UP,
)
from uuid import uuid4

from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.inventory import (
    Inventory,
    StockMovement,
    StockMovementType,
)
from app.models.sku import SKU, SKUStatus
from app.schemas.inventory import StockInboundCreate


MONEY_QUANTIZER = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    """金额统一保留两位小数。"""

    return value.quantize(
        MONEY_QUANTIZER,
        rounding=ROUND_HALF_UP,
    )


def generate_movement_no() -> str:
    """生成库存流水编号。"""

    random_part = uuid4().hex[:20].upper()

    return f"MOV-{random_part}"


def get_sku(
    db: Session,
    local_sku: str,
) -> SKU:
    """查询 SKU。"""

    normalized_local_sku = local_sku.strip().upper()

    statement = select(SKU).where(
        SKU.local_sku == normalized_local_sku
    )

    sku = db.scalar(statement)

    if sku is None:
        raise AppException(
            message="SKU 不存在",
            code="SKU_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={
                "local_sku": normalized_local_sku,
            },
        )

    return sku


def get_or_create_inventory(
    db: Session,
    sku: SKU,
    *,
    lock_for_update: bool = False,
) -> Inventory:
    """查询库存；兼容本模块上线前已经创建的 SKU。"""

    statement = select(Inventory).where(
        Inventory.sku_id == sku.id
    )

    if lock_for_update:
        statement = statement.with_for_update()

    inventory = db.scalar(statement)

    if inventory is not None:
        return inventory

    inventory = Inventory(
        sku_id=sku.id,
        on_hand_qty=0,
        reserved_qty=0,
        avg_cost=Decimal("0.00"),
    )

    db.add(inventory)
    db.flush()

    return inventory


def build_inventory_data(
    sku: SKU,
    inventory: Inventory,
) -> dict[str, object]:
    """构造当前库存返回数据。"""

    on_hand_qty = inventory.on_hand_qty
    reserved_qty = inventory.reserved_qty

    available_qty = (
        on_hand_qty
        - reserved_qty
    )

    inventory_value = quantize_money(
        Decimal(on_hand_qty)
        * inventory.avg_cost
    )

    return {
        "local_sku": sku.local_sku,
        "barcode": sku.barcode,
        "brand": sku.brand,
        "article_number": sku.article_number,
        "size": sku.size,
        "on_hand_qty": on_hand_qty,
        "reserved_qty": reserved_qty,
        "available_qty": available_qty,
        "avg_cost": inventory.avg_cost,
        "inventory_value": inventory_value,
        "updated_at": inventory.updated_at,
    }


def get_inventory(
    db: Session,
    local_sku: str,
) -> tuple[SKU, Inventory]:
    """查询某个 SKU 的当前库存。"""

    sku = get_sku(
        db=db,
        local_sku=local_sku,
    )

    try:
        inventory = get_or_create_inventory(
            db=db,
            sku=sku,
        )

        db.commit()
        db.refresh(inventory)

    except IntegrityError as exc:
        db.rollback()

        raise AppException(
            message="库存记录创建失败",
            code="INVENTORY_CREATE_FAILED",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc

    return sku, inventory


def inbound_stock(
    db: Session,
    payload: StockInboundCreate,
) -> tuple[SKU, Inventory, StockMovement]:
    """商品入库并重新计算移动平均成本。"""

    sku = get_sku(
        db=db,
        local_sku=payload.local_sku,
    )

    if sku.status != SKUStatus.ACTIVE:
        raise AppException(
            message="只有正常启用的 SKU 才能入库",
            code="SKU_NOT_ACTIVE",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "local_sku": sku.local_sku,
                "status": sku.status.value,
            },
        )

    try:
        inventory = get_or_create_inventory(
            db=db,
            sku=sku,
            lock_for_update=True,
        )

        before_qty = inventory.on_hand_qty
        before_avg_cost = inventory.avg_cost

        inbound_quantity = payload.quantity
        inbound_unit_cost = quantize_money(
            payload.unit_cost
        )

        after_qty = (
            before_qty
            + inbound_quantity
        )

        before_total_cost = (
            Decimal(before_qty)
            * before_avg_cost
        )

        inbound_total_cost = (
            Decimal(inbound_quantity)
            * inbound_unit_cost
        )

        after_avg_cost = quantize_money(
            (
                before_total_cost
                + inbound_total_cost
            )
            / Decimal(after_qty)
        )

        inventory.on_hand_qty = after_qty
        inventory.avg_cost = after_avg_cost

        movement = StockMovement(
            movement_no=generate_movement_no(),
            sku_id=sku.id,
            movement_type=StockMovementType.INBOUND,
            quantity_change=inbound_quantity,
            unit_cost=inbound_unit_cost,
            before_qty=before_qty,
            after_qty=after_qty,
            before_avg_cost=before_avg_cost,
            after_avg_cost=after_avg_cost,
            reference_no=payload.reference_no,
            note=payload.note,
        )

        db.add(movement)
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        raise AppException(
            message="入库操作失败，请重新提交",
            code="INBOUND_OPERATION_FAILED",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc

    db.refresh(inventory)
    db.refresh(movement)

    return sku, inventory, movement


def list_stock_movements(
    db: Session,
    local_sku: str,
) -> tuple[SKU, list[StockMovement]]:
    """查询某个 SKU 的全部库存流水。"""

    sku = get_sku(
        db=db,
        local_sku=local_sku,
    )

    statement = (
        select(StockMovement)
        .where(
            StockMovement.sku_id == sku.id
        )
        .order_by(
            StockMovement.id.desc()
        )
    )

    movements = list(
        db.scalars(statement).all()
    )

    return sku, movements