from decimal import Decimal
from uuid import uuid4

from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.inventory import Inventory
from app.models.sku import SKU, SKUStatus
from app.schemas.sku import SKUCreate


def generate_local_sku() -> str:
    """生成系统内部唯一 SKU 编码。"""

    random_part = uuid4().hex[:16].upper()
    return f"SKU-{random_part}"


def list_skus(db: Session) -> list[SKU]:
    """查询全部 SKU。"""

    statement = select(SKU).order_by(SKU.created_at.desc())
    return list(db.scalars(statement).all())


def create_sku(
    db: Session,
    payload: SKUCreate,
) -> SKU:
    """创建 SKU，并创建对应的初始库存记录。"""

    sku = SKU(
        local_sku=generate_local_sku(),
        **payload.model_dump(),
    )

    db.add(sku)

    try:
        db.flush()

        inventory = Inventory(
            sku_id=sku.id,
            on_hand_qty=0,
            reserved_qty=0,
            avg_cost=Decimal("0.00"),
        )

        db.add(inventory)
        db.commit()

    except IntegrityError as exc:
        db.rollback()

        raise AppException(
            message="条码或品牌、货号、尺码组合已经存在",
            code="SKU_ALREADY_EXISTS",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc

    db.refresh(sku)
    return sku


def get_sku_by_local_sku(
    db: Session,
    local_sku: str,
) -> SKU:
    """根据系统内部编码查询 SKU。"""

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


def get_sku_by_barcode(
    db: Session,
    barcode: str,
) -> SKU:
    """根据鞋盒条码查询 SKU。"""

    normalized_barcode = barcode.strip()

    statement = select(SKU).where(
        SKU.barcode == normalized_barcode
    )

    sku = db.scalar(statement)

    if sku is None:
        raise AppException(
            message="条码未建档，需要人工补录",
            code="SKU_BARCODE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={
                "barcode": normalized_barcode,
                "requires_manual_entry": True,
            },
        )

    return sku


def update_sku_status(
    db: Session,
    sku: SKU,
    new_status: SKUStatus,
) -> SKU:
    """修改 SKU 状态。"""

    sku.status = new_status

    db.commit()
    db.refresh(sku)

    return sku