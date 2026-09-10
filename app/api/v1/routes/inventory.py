from fastapi import (
    APIRouter,
    Depends,
    Path,
    status,
)
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.db.session import get_db
from app.schemas.inventory import (
    InventoryRead,
    StockInboundCreate,
    StockMovementRead,
)
from app.services.inventory_service import (
    build_inventory_data,
    get_inventory,
    inbound_stock,
    list_stock_movements,
)

router = APIRouter(
    prefix="/inventory",
)


def serialize_inventory(
    sku: object,
    inventory: object,
) -> dict[str, object]:
    """序列化当前库存。"""

    inventory_data = build_inventory_data(
        sku=sku,
        inventory=inventory,
    )

    return (
        InventoryRead
        .model_validate(inventory_data)
        .model_dump(mode="json")
    )


def serialize_movement(
    local_sku: str,
    movement: object,
) -> dict[str, object]:
    """序列化库存流水。"""

    movement_data = {
        "movement_no": movement.movement_no,
        "local_sku": local_sku,
        "movement_type": movement.movement_type,
        "quantity_change": movement.quantity_change,
        "unit_cost": movement.unit_cost,
        "before_qty": movement.before_qty,
        "after_qty": movement.after_qty,
        "before_avg_cost": movement.before_avg_cost,
        "after_avg_cost": movement.after_avg_cost,
        "reference_no": movement.reference_no,
        "note": movement.note,
        "created_at": movement.created_at,
    }

    return (
        StockMovementRead
        .model_validate(movement_data)
        .model_dump(mode="json")
    )


@router.post(
    "/inbounds",
    status_code=status.HTTP_201_CREATED,
    summary="商品入库",
)
def create_inbound(
    payload: StockInboundCreate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    sku, inventory, movement = inbound_stock(
        db=db,
        payload=payload,
    )

    return success_response(
        data={
            "inventory": serialize_inventory(
                sku=sku,
                inventory=inventory,
            ),
            "movement": serialize_movement(
                local_sku=sku.local_sku,
                movement=movement,
            ),
        },
        message="商品入库成功",
    )


@router.get(
    "/{local_sku}/movements",
    summary="查询 SKU 库存流水",
)
def get_movements(
    local_sku: str = Path(
        min_length=1,
        max_length=32,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    sku, movements = list_stock_movements(
        db=db,
        local_sku=local_sku,
    )

    movement_data = [
        serialize_movement(
            local_sku=sku.local_sku,
            movement=movement,
        )
        for movement in movements
    ]

    return success_response(
        data=movement_data,
    )


@router.get(
    "/{local_sku}",
    summary="查询 SKU 当前库存",
)
def get_current_inventory(
    local_sku: str = Path(
        min_length=1,
        max_length=32,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    sku, inventory = get_inventory(
        db=db,
        local_sku=local_sku,
    )

    return success_response(
        data=serialize_inventory(
            sku=sku,
            inventory=inventory,
        ),
    )