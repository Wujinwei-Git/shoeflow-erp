from decimal import Decimal
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
from app.models.sales import (
    SalesItem,
    SalesOrder,
    SaleStatus,
)
from app.models.sku import SKU, SKUStatus
from app.schemas.sales import SaleCreate
from app.services.inventory_service import (
    generate_movement_no,
    quantize_money,
)


def generate_sale_no() -> str:
    """生成系统销售单号。"""

    random_part = uuid4().hex[:20].upper()

    return f"SALE-{random_part}"


def get_sku_by_local_sku(
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


def create_sale(
    db: Session,
    payload: SaleCreate,
    *,
    commit: bool = True,
) -> SalesOrder:
    """创建销售单并扣减库存，可加入调用方的原子事务。"""

    sales_order = SalesOrder(
        sale_no=generate_sale_no(),
        status=SaleStatus.COMPLETED,
        total_amount=Decimal("0.00"),
        total_cost=Decimal("0.00"),
        gross_profit=Decimal("0.00"),
        note=payload.note,
    )

    try:
        db.add(sales_order)
        db.flush()

        total_amount = Decimal("0.00")
        total_cost = Decimal("0.00")

        sorted_items = sorted(
            payload.items,
            key=lambda item: item.local_sku,
        )

        for request_item in sorted_items:
            sku = get_sku_by_local_sku(
                db=db,
                local_sku=request_item.local_sku,
            )

            if sku.status != SKUStatus.ACTIVE:
                raise AppException(
                    message="只有正常启用的 SKU 才能销售",
                    code="SKU_NOT_ACTIVE",
                    status_code=status.HTTP_409_CONFLICT,
                    details={
                        "local_sku": sku.local_sku,
                        "status": sku.status.value,
                    },
                )

            inventory_statement = (
                select(Inventory)
                .where(
                    Inventory.sku_id == sku.id
                )
                .with_for_update()
            )

            inventory = db.scalar(
                inventory_statement
            )

            if inventory is None:
                raise AppException(
                    message="可用库存不足",
                    code="INSUFFICIENT_STOCK",
                    status_code=status.HTTP_409_CONFLICT,
                    details={
                        "local_sku": sku.local_sku,
                        "available_qty": 0,
                        "requested_qty": request_item.quantity,
                    },
                )

            available_qty = (
                inventory.on_hand_qty
                - inventory.reserved_qty
            )

            if available_qty < request_item.quantity:
                raise AppException(
                    message="可用库存不足",
                    code="INSUFFICIENT_STOCK",
                    status_code=status.HTTP_409_CONFLICT,
                    details={
                        "local_sku": sku.local_sku,
                        "available_qty": available_qty,
                        "requested_qty": request_item.quantity,
                    },
                )

            before_qty = inventory.on_hand_qty
            after_qty = (
                before_qty
                - request_item.quantity
            )

            unit_price = quantize_money(
                request_item.unit_price
            )

            unit_cost = quantize_money(
                inventory.avg_cost
            )

            line_amount = quantize_money(
                unit_price
                * Decimal(request_item.quantity)
            )

            line_cost = quantize_money(
                unit_cost
                * Decimal(request_item.quantity)
            )

            line_profit = quantize_money(
                line_amount
                - line_cost
            )

            sales_item = SalesItem(
                sales_order_id=sales_order.id,
                sku_id=sku.id,
                quantity=request_item.quantity,
                unit_price=unit_price,
                unit_cost=unit_cost,
                line_amount=line_amount,
                line_cost=line_cost,
                line_profit=line_profit,
            )

            movement = StockMovement(
                movement_no=generate_movement_no(),
                sku_id=sku.id,
                movement_type=StockMovementType.SALE,
                quantity_change=-request_item.quantity,
                unit_cost=unit_cost,
                before_qty=before_qty,
                after_qty=after_qty,
                before_avg_cost=inventory.avg_cost,
                after_avg_cost=inventory.avg_cost,
                reference_no=sales_order.sale_no,
                note="销售出库",
            )

            inventory.on_hand_qty = after_qty

            db.add(sales_item)
            db.add(movement)

            total_amount += line_amount
            total_cost += line_cost

        sales_order.total_amount = quantize_money(
            total_amount
        )

        sales_order.total_cost = quantize_money(
            total_cost
        )

        sales_order.gross_profit = quantize_money(
            total_amount
            - total_cost
        )

        db.flush()

        if commit:
            db.commit()

    except AppException:
        if commit:
            db.rollback()
        raise

    except IntegrityError as exc:
        if commit:
            db.rollback()

        raise AppException(
            message="销售操作失败，请重新提交",
            code="SALE_OPERATION_FAILED",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc

    if commit:
        db.refresh(sales_order)

    return sales_order


def get_sales_order(
    db: Session,
    sale_no: str,
) -> SalesOrder:
    """根据销售单号查询销售单。"""

    normalized_sale_no = sale_no.strip().upper()

    statement = select(SalesOrder).where(
        SalesOrder.sale_no == normalized_sale_no
    )

    sales_order = db.scalar(statement)

    if sales_order is None:
        raise AppException(
            message="销售单不存在",
            code="SALE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={
                "sale_no": normalized_sale_no,
            },
        )

    return sales_order


def build_sale_data(
    db: Session,
    sales_order: SalesOrder,
) -> dict[str, object]:
    """构造完整销售单返回数据。"""

    item_statement = (
        select(SalesItem)
        .where(
            SalesItem.sales_order_id
            == sales_order.id
        )
        .order_by(SalesItem.id.asc())
    )

    sales_items = list(
        db.scalars(item_statement).all()
    )

    item_data: list[dict[str, object]] = []

    for sales_item in sales_items:
        sku_statement = select(SKU).where(
            SKU.id == sales_item.sku_id
        )

        sku = db.scalar(sku_statement)

        if sku is None:
            continue

        item_data.append(
            {
                "local_sku": sku.local_sku,
                "barcode": sku.barcode,
                "brand": sku.brand,
                "article_number": sku.article_number,
                "size": sku.size,
                "quantity": sales_item.quantity,
                "unit_price": sales_item.unit_price,
                "unit_cost": sales_item.unit_cost,
                "line_amount": sales_item.line_amount,
                "line_cost": sales_item.line_cost,
                "line_profit": sales_item.line_profit,
            }
        )

    return {
        "sale_no": sales_order.sale_no,
        "status": sales_order.status,
        "total_amount": sales_order.total_amount,
        "total_cost": sales_order.total_cost,
        "gross_profit": sales_order.gross_profit,
        "note": sales_order.note,
        "sold_at": sales_order.sold_at,
        "items": item_data,
    }


def list_sales_orders(
    db: Session,
    limit: int,
) -> list[SalesOrder]:
    """查询最近的销售记录。"""

    statement = (
        select(SalesOrder)
        .order_by(SalesOrder.id.desc())
        .limit(limit)
    )

    return list(
        db.scalars(statement).all()
    )
