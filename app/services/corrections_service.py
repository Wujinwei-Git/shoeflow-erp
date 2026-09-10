from decimal import Decimal
from uuid import uuid4

from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.corrections import InventoryCorrection
from app.models.inventory import (
    Inventory,
    StockMovement,
    StockMovementType,
)
from app.models.sku import SKU
from app.schemas.corrections import (
    InventoryCorrectionCreate,
)
from app.services.inventory_service import (
    generate_movement_no,
    quantize_money,
)


def generate_correction_no() -> str:
    """生成库存校正单号。"""

    random_part = uuid4().hex[:20].upper()

    return f"COR-{random_part}"


def get_sku(
    db: Session,
    local_sku: str,
) -> SKU:
    """根据内部编码查询 SKU。"""

    statement = select(SKU).where(
        SKU.local_sku == local_sku
    )

    sku = db.scalar(statement)

    if sku is None:
        raise AppException(
            message="SKU 不存在",
            code="SKU_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={
                "local_sku": local_sku,
            },
        )

    return sku


def get_inventory_for_update(
    db: Session,
    sku: SKU,
) -> Inventory:
    """查询并锁定库存记录。"""

    statement = (
        select(Inventory)
        .where(
            Inventory.sku_id == sku.id
        )
        .with_for_update()
    )

    inventory = db.scalar(statement)

    if inventory is None:
        inventory = Inventory(
            sku_id=sku.id,
            on_hand_qty=0,
            reserved_qty=0,
            avg_cost=Decimal("0.00"),
        )

        db.add(inventory)
        db.flush()

    return inventory


def create_inventory_correction(
    db: Session,
    payload: InventoryCorrectionCreate,
) -> InventoryCorrection:
    """执行库存数量校正。"""

    try:
        sku = get_sku(
            db=db,
            local_sku=payload.local_sku,
        )

        inventory = get_inventory_for_update(
            db=db,
            sku=sku,
        )

        before_qty = inventory.on_hand_qty
        before_avg_cost = inventory.avg_cost

        after_qty = (
            before_qty
            + payload.quantity_change
        )

        if after_qty < inventory.reserved_qty:
            raise AppException(
                message="校正后库存不能小于已预留库存",
                code="CORRECTION_STOCK_TOO_LOW",
                status_code=status.HTTP_409_CONFLICT,
                details={
                    "local_sku": sku.local_sku,
                    "on_hand_qty": before_qty,
                    "reserved_qty": inventory.reserved_qty,
                    "quantity_change": payload.quantity_change,
                    "after_qty": after_qty,
                },
            )

        if payload.quantity_change < 0:
            correction_unit_cost = (
                before_avg_cost
            )

            after_avg_cost = (
                before_avg_cost
            )

        else:
            if payload.unit_cost is not None:
                correction_unit_cost = quantize_money(
                    payload.unit_cost
                )

            elif before_avg_cost > 0:
                correction_unit_cost = (
                    before_avg_cost
                )

            else:
                raise AppException(
                    message=(
                        "当前SKU没有可用平均成本，"
                        "增加库存时必须填写单位成本"
                    ),
                    code="CORRECTION_UNIT_COST_REQUIRED",
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    details={
                        "local_sku": sku.local_sku,
                    },
                )

            current_inventory_value = (
                Decimal(before_qty)
                * before_avg_cost
            )

            added_inventory_value = (
                Decimal(payload.quantity_change)
                * correction_unit_cost
            )

            after_avg_cost = quantize_money(
                (
                    current_inventory_value
                    + added_inventory_value
                )
                / Decimal(after_qty)
            )

        inventory_value_change = quantize_money(
            Decimal(payload.quantity_change)
            * correction_unit_cost
        )

        inventory.on_hand_qty = after_qty
        inventory.avg_cost = after_avg_cost

        correction = InventoryCorrection(
            correction_no=generate_correction_no(),
            sku_id=sku.id,
            quantity_change=payload.quantity_change,
            unit_cost=correction_unit_cost,
            inventory_value_change=(
                inventory_value_change
            ),
            before_qty=before_qty,
            after_qty=after_qty,
            before_avg_cost=before_avg_cost,
            after_avg_cost=after_avg_cost,
            reason=payload.reason,
            note=payload.note,
        )

        movement = StockMovement(
            movement_no=generate_movement_no(),
            sku_id=sku.id,
            movement_type=(
                StockMovementType.ADJUSTMENT
            ),
            quantity_change=(
                payload.quantity_change
            ),
            unit_cost=correction_unit_cost,
            before_qty=before_qty,
            after_qty=after_qty,
            before_avg_cost=before_avg_cost,
            after_avg_cost=after_avg_cost,
            reference_no=correction.correction_no,
            note=(
                f"库存数量校正："
                f"{payload.reason.value}"
            ),
        )

        db.add(correction)
        db.add(movement)
        db.commit()

    except AppException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()

        raise AppException(
            message="库存校正失败，请重新提交",
            code="INVENTORY_CORRECTION_FAILED",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc

    db.refresh(correction)

    return correction


def get_correction(
    db: Session,
    correction_no: str,
) -> InventoryCorrection:
    """查询库存校正记录。"""

    normalized_correction_no = (
        correction_no.strip().upper()
    )

    statement = select(
        InventoryCorrection
    ).where(
        InventoryCorrection.correction_no
        == normalized_correction_no
    )

    correction = db.scalar(statement)

    if correction is None:
        raise AppException(
            message="库存校正记录不存在",
            code="CORRECTION_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={
                "correction_no": (
                    normalized_correction_no
                ),
            },
        )

    return correction


def list_corrections(
    db: Session,
    limit: int,
) -> list[InventoryCorrection]:
    """查询最近库存校正记录。"""

    statement = (
        select(InventoryCorrection)
        .order_by(
            InventoryCorrection.id.desc()
        )
        .limit(limit)
    )

    return list(
        db.scalars(statement).all()
    )


def build_correction_data(
    db: Session,
    correction: InventoryCorrection,
) -> dict[str, object]:
    """构造库存校正返回数据。"""

    statement = select(SKU).where(
        SKU.id == correction.sku_id
    )

    sku = db.scalar(statement)

    if sku is None:
        raise AppException(
            message="库存校正对应的SKU不存在",
            code="SKU_NOT_FOUND",
            status_code=status.HTTP_409_CONFLICT,
        )

    return {
        "correction_no": correction.correction_no,
        "local_sku": sku.local_sku,
        "barcode": sku.barcode,
        "brand": sku.brand,
        "article_number": sku.article_number,
        "size": sku.size,
        "quantity_change": (
            correction.quantity_change
        ),
        "unit_cost": correction.unit_cost,
        "inventory_value_change": (
            correction.inventory_value_change
        ),
        "before_qty": correction.before_qty,
        "after_qty": correction.after_qty,
        "before_avg_cost": (
            correction.before_avg_cost
        ),
        "after_avg_cost": (
            correction.after_avg_cost
        ),
        "reason": correction.reason,
        "note": correction.note,
        "created_at": correction.created_at,
    }