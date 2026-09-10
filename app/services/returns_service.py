from decimal import Decimal
from uuid import uuid4

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
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
from app.models.sku import SKU
from app.schemas.returns import (
    ReturnCreate,
    SaleReverseCreate,
)
from app.services.inventory_service import (
    generate_movement_no,
    quantize_money,
)


def generate_return_no() -> str:
    """生成退货或冲销单号。"""

    random_part = uuid4().hex[:20].upper()

    return f"RET-{random_part}"


def get_sales_order_for_update(
    db: Session,
    sale_no: str,
) -> SalesOrder:
    """查询并锁定原销售单。"""

    statement = (
        select(SalesOrder)
        .where(
            SalesOrder.sale_no == sale_no
        )
        .with_for_update()
    )

    sales_order = db.scalar(statement)

    if sales_order is None:
        raise AppException(
            message="原销售单不存在",
            code="SALE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={
                "sale_no": sale_no,
            },
        )

    return sales_order


def get_sku_by_local_sku(
    db: Session,
    local_sku: str,
) -> SKU:
    """查询 SKU。"""

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


def get_sales_item(
    db: Session,
    sales_order_id: int,
    sku_id: int,
) -> SalesItem:
    """查询原销售单中的指定商品。"""

    statement = select(SalesItem).where(
        SalesItem.sales_order_id
        == sales_order_id,
        SalesItem.sku_id == sku_id,
    )

    sales_item = db.scalar(statement)

    if sales_item is None:
        raise AppException(
            message="原销售单中不存在该 SKU",
            code="SALE_ITEM_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return sales_item


def get_returned_quantity(
    db: Session,
    sales_order_id: int,
    sales_item_id: int,
) -> int:
    """查询某条销售明细累计已退数量。"""

    statement = (
        select(
            func.coalesce(
                func.sum(ReturnItem.quantity),
                0,
            )
        )
        .join(
            ReturnOrder,
            ReturnOrder.id
            == ReturnItem.return_order_id,
        )
        .where(
            ReturnOrder.sales_order_id
            == sales_order_id,
            ReturnItem.sales_item_id
            == sales_item_id,
        )
    )

    result = db.scalar(statement)

    return int(result or 0)


def restore_inventory(
    db: Session,
    *,
    sku: SKU,
    quantity: int,
    unit_cost: Decimal,
    movement_type: StockMovementType,
    reference_no: str,
    note: str,
) -> None:
    """按照原销售成本将商品恢复到库存。"""

    statement = (
        select(Inventory)
        .where(
            Inventory.sku_id == sku.id
        )
        .with_for_update()
    )

    inventory = db.scalar(statement)

    if inventory is None:
        raise AppException(
            message="SKU 库存记录不存在",
            code="INVENTORY_NOT_FOUND",
            status_code=status.HTTP_409_CONFLICT,
            details={
                "local_sku": sku.local_sku,
            },
        )

    before_qty = inventory.on_hand_qty
    before_avg_cost = inventory.avg_cost

    after_qty = (
        before_qty
        + quantity
    )

    current_inventory_cost = (
        Decimal(before_qty)
        * before_avg_cost
    )

    returned_inventory_cost = (
        Decimal(quantity)
        * unit_cost
    )

    after_avg_cost = quantize_money(
        (
            current_inventory_cost
            + returned_inventory_cost
        )
        / Decimal(after_qty)
    )

    inventory.on_hand_qty = after_qty
    inventory.avg_cost = after_avg_cost

    movement = StockMovement(
        movement_no=generate_movement_no(),
        sku_id=sku.id,
        movement_type=movement_type,
        quantity_change=quantity,
        unit_cost=unit_cost,
        before_qty=before_qty,
        after_qty=after_qty,
        before_avg_cost=before_avg_cost,
        after_avg_cost=after_avg_cost,
        reference_no=reference_no,
        note=note,
    )

    db.add(movement)


def update_sale_return_status(
    db: Session,
    sales_order: SalesOrder,
) -> None:
    """根据累计退货数量更新原销售单状态。"""

    statement = select(SalesItem).where(
        SalesItem.sales_order_id
        == sales_order.id
    )

    sales_items = list(
        db.scalars(statement).all()
    )

    all_returned = True
    any_returned = False

    for sales_item in sales_items:
        returned_quantity = get_returned_quantity(
            db=db,
            sales_order_id=sales_order.id,
            sales_item_id=sales_item.id,
        )

        if returned_quantity > 0:
            any_returned = True

        if returned_quantity < sales_item.quantity:
            all_returned = False

    if all_returned:
        sales_order.status = SaleStatus.RETURNED

    elif any_returned:
        sales_order.status = (
            SaleStatus.PARTIALLY_RETURNED
        )


def create_customer_return(
    db: Session,
    payload: ReturnCreate,
) -> ReturnOrder:
    """创建顾客退货并恢复库存。"""

    try:
        sales_order = get_sales_order_for_update(
            db=db,
            sale_no=payload.sale_no,
        )

        if sales_order.status in {
            SaleStatus.RETURNED,
            SaleStatus.REVERSED,
        }:
            raise AppException(
                message="该销售单已经全部退货或冲销",
                code="SALE_NOT_RETURNABLE",
                status_code=status.HTTP_409_CONFLICT,
                details={
                    "sale_no": sales_order.sale_no,
                    "status": sales_order.status.value,
                },
            )

        return_order = ReturnOrder(
            return_no=generate_return_no(),
            sales_order_id=sales_order.id,
            return_type=ReturnType.CUSTOMER_RETURN,
            total_amount=Decimal("0.00"),
            total_cost=Decimal("0.00"),
            gross_profit_reversal=Decimal("0.00"),
            note=payload.note,
        )

        db.add(return_order)
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

            sales_item = get_sales_item(
                db=db,
                sales_order_id=sales_order.id,
                sku_id=sku.id,
            )

            returned_quantity = get_returned_quantity(
                db=db,
                sales_order_id=sales_order.id,
                sales_item_id=sales_item.id,
            )

            returnable_quantity = (
                sales_item.quantity
                - returned_quantity
            )

            if request_item.quantity > returnable_quantity:
                raise AppException(
                    message="退货数量超过可退数量",
                    code="RETURN_QUANTITY_EXCEEDED",
                    status_code=status.HTTP_409_CONFLICT,
                    details={
                        "local_sku": sku.local_sku,
                        "sold_quantity": sales_item.quantity,
                        "returned_quantity": returned_quantity,
                        "returnable_quantity": returnable_quantity,
                        "requested_quantity": request_item.quantity,
                    },
                )

            line_amount = quantize_money(
                sales_item.unit_price
                * Decimal(request_item.quantity)
            )

            line_cost = quantize_money(
                sales_item.unit_cost
                * Decimal(request_item.quantity)
            )

            line_profit_reversal = quantize_money(
                line_amount
                - line_cost
            )

            return_item = ReturnItem(
                return_order_id=return_order.id,
                sales_item_id=sales_item.id,
                sku_id=sku.id,
                quantity=request_item.quantity,
                unit_price=sales_item.unit_price,
                unit_cost=sales_item.unit_cost,
                line_amount=line_amount,
                line_cost=line_cost,
                line_profit_reversal=line_profit_reversal,
            )

            db.add(return_item)

            restore_inventory(
                db=db,
                sku=sku,
                quantity=request_item.quantity,
                unit_cost=sales_item.unit_cost,
                movement_type=StockMovementType.RETURN,
                reference_no=return_order.return_no,
                note="销售退货回库",
            )

            total_amount += line_amount
            total_cost += line_cost

        return_order.total_amount = quantize_money(
            total_amount
        )

        return_order.total_cost = quantize_money(
            total_cost
        )

        return_order.gross_profit_reversal = (
            quantize_money(
                total_amount
                - total_cost
            )
        )

        db.flush()

        update_sale_return_status(
            db=db,
            sales_order=sales_order,
        )

        db.commit()

    except AppException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()

        raise AppException(
            message="退货操作失败，请重新提交",
            code="RETURN_OPERATION_FAILED",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc

    db.refresh(return_order)

    return return_order


def reverse_sale(
    db: Session,
    sale_no: str,
    payload: SaleReverseCreate,
) -> ReturnOrder:
    """冲销一张没有发生过退货的完整销售单。"""

    normalized_sale_no = sale_no.strip().upper()

    try:
        sales_order = get_sales_order_for_update(
            db=db,
            sale_no=normalized_sale_no,
        )

        if sales_order.status != SaleStatus.COMPLETED:
            raise AppException(
                message="只有未退货、未冲销的销售单才能整单冲销",
                code="SALE_NOT_REVERSIBLE",
                status_code=status.HTTP_409_CONFLICT,
                details={
                    "sale_no": sales_order.sale_no,
                    "status": sales_order.status.value,
                },
            )

        return_order = ReturnOrder(
            return_no=generate_return_no(),
            sales_order_id=sales_order.id,
            return_type=ReturnType.SALE_REVERSAL,
            total_amount=sales_order.total_amount,
            total_cost=sales_order.total_cost,
            gross_profit_reversal=(
                sales_order.gross_profit
            ),
            note=payload.note,
        )

        db.add(return_order)
        db.flush()

        item_statement = select(SalesItem).where(
            SalesItem.sales_order_id
            == sales_order.id
        )

        sales_items = list(
            db.scalars(item_statement).all()
        )

        for sales_item in sales_items:
            sku_statement = select(SKU).where(
                SKU.id == sales_item.sku_id
            )

            sku = db.scalar(sku_statement)

            if sku is None:
                raise AppException(
                    message="销售明细对应的 SKU 不存在",
                    code="SKU_NOT_FOUND",
                    status_code=status.HTTP_409_CONFLICT,
                )

            return_item = ReturnItem(
                return_order_id=return_order.id,
                sales_item_id=sales_item.id,
                sku_id=sku.id,
                quantity=sales_item.quantity,
                unit_price=sales_item.unit_price,
                unit_cost=sales_item.unit_cost,
                line_amount=sales_item.line_amount,
                line_cost=sales_item.line_cost,
                line_profit_reversal=(
                    sales_item.line_profit
                ),
            )

            db.add(return_item)

            restore_inventory(
                db=db,
                sku=sku,
                quantity=sales_item.quantity,
                unit_cost=sales_item.unit_cost,
                movement_type=(
                    StockMovementType.REVERSAL
                ),
                reference_no=return_order.return_no,
                note="销售冲销回库",
            )

        sales_order.status = SaleStatus.REVERSED

        db.commit()

    except AppException:
        db.rollback()
        raise

    except IntegrityError as exc:
        db.rollback()

        raise AppException(
            message="销售冲销失败，请重新提交",
            code="SALE_REVERSAL_FAILED",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc

    db.refresh(return_order)

    return return_order


def get_return_order(
    db: Session,
    return_no: str,
) -> ReturnOrder:
    """根据退货单号查询退货单。"""

    normalized_return_no = (
        return_no.strip().upper()
    )

    statement = select(ReturnOrder).where(
        ReturnOrder.return_no
        == normalized_return_no
    )

    return_order = db.scalar(statement)

    if return_order is None:
        raise AppException(
            message="退货或冲销记录不存在",
            code="RETURN_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={
                "return_no": normalized_return_no,
            },
        )

    return return_order


def build_return_data(
    db: Session,
    return_order: ReturnOrder,
) -> dict[str, object]:
    """构造完整退货记录。"""

    sales_order_statement = (
        select(SalesOrder)
        .where(
            SalesOrder.id
            == return_order.sales_order_id
        )
    )

    sales_order = db.scalar(
        sales_order_statement
    )

    item_statement = (
        select(ReturnItem)
        .where(
            ReturnItem.return_order_id
            == return_order.id
        )
        .order_by(ReturnItem.id.asc())
    )

    return_items = list(
        db.scalars(item_statement).all()
    )

    item_data: list[dict[str, object]] = []

    for return_item in return_items:
        sku_statement = select(SKU).where(
            SKU.id == return_item.sku_id
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
                "quantity": return_item.quantity,
                "unit_price": return_item.unit_price,
                "unit_cost": return_item.unit_cost,
                "line_amount": return_item.line_amount,
                "line_cost": return_item.line_cost,
                "line_profit_reversal": (
                    return_item.line_profit_reversal
                ),
            }
        )

    return {
        "return_no": return_order.return_no,
        "sale_no": (
            sales_order.sale_no
            if sales_order is not None
            else ""
        ),
        "return_type": return_order.return_type,
        "total_amount": return_order.total_amount,
        "total_cost": return_order.total_cost,
        "gross_profit_reversal": (
            return_order.gross_profit_reversal
        ),
        "note": return_order.note,
        "returned_at": return_order.returned_at,
        "items": item_data,
    }


def list_return_orders(
    db: Session,
    limit: int,
) -> list[ReturnOrder]:
    """查询最近退货和冲销记录。"""

    statement = (
        select(ReturnOrder)
        .order_by(ReturnOrder.id.desc())
        .limit(limit)
    )

    return list(
        db.scalars(statement).all()
    )