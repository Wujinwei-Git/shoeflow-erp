from collections import defaultdict
from datetime import (
    date,
    datetime,
    time,
    timedelta,
)
from decimal import Decimal
from typing import Any

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.inventory import Inventory
from app.models.returns import (
    ReturnItem,
    ReturnOrder,
    ReturnType,
)
from app.models.sales import (
    SalesItem,
    SalesOrder,
)
from app.models.sku import SKU, SKUStatus
from app.services.inventory_service import (
    quantize_money,
)


ZERO_MONEY = Decimal("0.00")


def validate_date_range(
    date_from: date | None,
    date_to: date | None,
) -> None:
    """检查开始日期和结束日期。"""

    if (
        date_from is not None
        and date_to is not None
        and date_from > date_to
    ):
        raise AppException(
            message="开始日期不能晚于结束日期",
            code="INVALID_DATE_RANGE",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


def apply_date_range(
    statement: Any,
    datetime_column: Any,
    date_from: date | None,
    date_to: date | None,
) -> Any:
    """为 SQL 查询添加日期范围。"""

    if date_from is not None:
        start_datetime = datetime.combine(
            date_from,
            time.min,
        )

        statement = statement.where(
            datetime_column >= start_datetime
        )

    if date_to is not None:
        end_datetime = datetime.combine(
            date_to + timedelta(days=1),
            time.min,
        )

        statement = statement.where(
            datetime_column < end_datetime
        )

    return statement


def get_inventory_rows(
    db: Session,
) -> list[tuple[SKU, Inventory | None]]:
    """查询全部 SKU 及库存。"""

    statement = (
        select(SKU, Inventory)
        .outerjoin(
            Inventory,
            Inventory.sku_id == SKU.id,
        )
        .order_by(
            SKU.brand.asc(),
            SKU.article_number.asc(),
            SKU.size.asc(),
        )
    )

    return list(
        db.execute(statement).all()
    )


def build_inventory_item(
    sku: SKU,
    inventory: Inventory | None,
) -> dict[str, object]:
    """构造单个 SKU 的库存统计。"""

    on_hand_qty = (
        inventory.on_hand_qty
        if inventory is not None
        else 0
    )

    reserved_qty = (
        inventory.reserved_qty
        if inventory is not None
        else 0
    )

    avg_cost = (
        inventory.avg_cost
        if inventory is not None
        else ZERO_MONEY
    )

    available_qty = (
        on_hand_qty
        - reserved_qty
    )

    inventory_value = quantize_money(
        Decimal(on_hand_qty)
        * avg_cost
    )

    return {
        "local_sku": sku.local_sku,
        "barcode": sku.barcode,
        "brand": sku.brand,
        "article_number": sku.article_number,
        "size": sku.size,
        "status": sku.status,
        "on_hand_qty": on_hand_qty,
        "reserved_qty": reserved_qty,
        "available_qty": available_qty,
        "avg_cost": avg_cost,
        "inventory_value": inventory_value,
    }


def get_inventory_analytics(
    db: Session,
    low_stock_threshold: int = 2,
) -> dict[str, object]:
    """计算当前库存汇总。"""

    rows = get_inventory_rows(db)

    sku_count = len(rows)
    active_sku_count = 0

    total_on_hand_qty = 0
    total_reserved_qty = 0
    total_available_qty = 0
    total_inventory_value = ZERO_MONEY

    low_stock_sku_count = 0

    for sku, inventory in rows:
        item = build_inventory_item(
            sku=sku,
            inventory=inventory,
        )

        if sku.status == SKUStatus.ACTIVE:
            active_sku_count += 1

        total_on_hand_qty += int(
            item["on_hand_qty"]
        )

        total_reserved_qty += int(
            item["reserved_qty"]
        )

        total_available_qty += int(
            item["available_qty"]
        )

        total_inventory_value += Decimal(
            item["inventory_value"]
        )

        if (
            sku.status == SKUStatus.ACTIVE
            and int(item["available_qty"])
            <= low_stock_threshold
        ):
            low_stock_sku_count += 1

    return {
        "sku_count": sku_count,
        "active_sku_count": active_sku_count,
        "on_hand_qty": total_on_hand_qty,
        "reserved_qty": total_reserved_qty,
        "available_qty": total_available_qty,
        "inventory_value": quantize_money(
            total_inventory_value
        ),
        "low_stock_sku_count": (
            low_stock_sku_count
        ),
    }


def get_sales_orders_in_range(
    db: Session,
    date_from: date | None,
    date_to: date | None,
) -> list[SalesOrder]:
    """查询日期范围内的原始销售单。"""

    statement = select(SalesOrder)

    statement = apply_date_range(
        statement=statement,
        datetime_column=SalesOrder.sold_at,
        date_from=date_from,
        date_to=date_to,
    )

    return list(
        db.scalars(statement).all()
    )


def get_return_orders_in_range(
    db: Session,
    date_from: date | None,
    date_to: date | None,
) -> list[ReturnOrder]:
    """查询日期范围内的退货和冲销记录。"""

    statement = select(ReturnOrder)

    statement = apply_date_range(
        statement=statement,
        datetime_column=ReturnOrder.returned_at,
        date_from=date_from,
        date_to=date_to,
    )

    return list(
        db.scalars(statement).all()
    )


def get_sales_items_in_range(
    db: Session,
    date_from: date | None,
    date_to: date | None,
) -> list[SalesItem]:
    """查询日期范围内的销售明细。"""

    statement = (
        select(SalesItem)
        .join(
            SalesOrder,
            SalesOrder.id
            == SalesItem.sales_order_id,
        )
    )

    statement = apply_date_range(
        statement=statement,
        datetime_column=SalesOrder.sold_at,
        date_from=date_from,
        date_to=date_to,
    )

    return list(
        db.scalars(statement).all()
    )


def get_return_items_in_range(
    db: Session,
    date_from: date | None,
    date_to: date | None,
) -> list[tuple[ReturnItem, ReturnType]]:
    """查询日期范围内的退货和冲销明细。"""

    statement = (
        select(
            ReturnItem,
            ReturnOrder.return_type,
        )
        .join(
            ReturnOrder,
            ReturnOrder.id
            == ReturnItem.return_order_id,
        )
    )

    statement = apply_date_range(
        statement=statement,
        datetime_column=ReturnOrder.returned_at,
        date_from=date_from,
        date_to=date_to,
    )

    return list(
        db.execute(statement).all()
    )


def get_sales_analytics(
    db: Session,
    date_from: date | None,
    date_to: date | None,
) -> dict[str, object]:
    """计算销售、退货、冲销和净利润。"""

    sales_orders = get_sales_orders_in_range(
        db=db,
        date_from=date_from,
        date_to=date_to,
    )

    return_orders = get_return_orders_in_range(
        db=db,
        date_from=date_from,
        date_to=date_to,
    )

    sales_items = get_sales_items_in_range(
        db=db,
        date_from=date_from,
        date_to=date_to,
    )

    return_items = get_return_items_in_range(
        db=db,
        date_from=date_from,
        date_to=date_to,
    )

    gross_sales_amount = sum(
        (
            order.total_amount
            for order in sales_orders
        ),
        ZERO_MONEY,
    )

    gross_sales_cost = sum(
        (
            order.total_cost
            for order in sales_orders
        ),
        ZERO_MONEY,
    )

    gross_sales_profit = sum(
        (
            order.gross_profit
            for order in sales_orders
        ),
        ZERO_MONEY,
    )

    customer_returns = [
        order
        for order in return_orders
        if order.return_type
        == ReturnType.CUSTOMER_RETURN
    ]

    reversals = [
        order
        for order in return_orders
        if order.return_type
        == ReturnType.SALE_REVERSAL
    ]

    return_amount = sum(
        (
            order.total_amount
            for order in customer_returns
        ),
        ZERO_MONEY,
    )

    return_cost = sum(
        (
            order.total_cost
            for order in customer_returns
        ),
        ZERO_MONEY,
    )

    return_profit_reversal = sum(
        (
            order.gross_profit_reversal
            for order in customer_returns
        ),
        ZERO_MONEY,
    )

    reversal_amount = sum(
        (
            order.total_amount
            for order in reversals
        ),
        ZERO_MONEY,
    )

    reversal_cost = sum(
        (
            order.total_cost
            for order in reversals
        ),
        ZERO_MONEY,
    )

    reversal_profit = sum(
        (
            order.gross_profit_reversal
            for order in reversals
        ),
        ZERO_MONEY,
    )

    total_deduction_amount = (
        return_amount
        + reversal_amount
    )

    total_deduction_cost = (
        return_cost
        + reversal_cost
    )

    total_profit_reversal = (
        return_profit_reversal
        + reversal_profit
    )

    gross_units_sold = sum(
        item.quantity
        for item in sales_items
    )

    returned_units = sum(
        item.quantity
        for item, return_type in return_items
        if return_type
        == ReturnType.CUSTOMER_RETURN
    )

    reversed_units = sum(
        item.quantity
        for item, return_type in return_items
        if return_type
        == ReturnType.SALE_REVERSAL
    )

    net_units_sold = (
        gross_units_sold
        - returned_units
        - reversed_units
    )

    return {
        "sales_order_count": len(sales_orders),
        "return_order_count": len(
            customer_returns
        ),
        "reversal_order_count": len(
            reversals
        ),
        "gross_units_sold": gross_units_sold,
        "returned_units": returned_units,
        "reversed_units": reversed_units,
        "net_units_sold": net_units_sold,
        "gross_sales_amount": quantize_money(
            gross_sales_amount
        ),
        "gross_sales_cost": quantize_money(
            gross_sales_cost
        ),
        "gross_sales_profit": quantize_money(
            gross_sales_profit
        ),
        "return_amount": quantize_money(
            return_amount
        ),
        "return_cost": quantize_money(
            return_cost
        ),
        "return_profit_reversal": quantize_money(
            return_profit_reversal
        ),
        "reversal_amount": quantize_money(
            reversal_amount
        ),
        "reversal_cost": quantize_money(
            reversal_cost
        ),
        "reversal_profit": quantize_money(
            reversal_profit
        ),
        "net_sales_amount": quantize_money(
            gross_sales_amount
            - total_deduction_amount
        ),
        "net_sales_cost": quantize_money(
            gross_sales_cost
            - total_deduction_cost
        ),
        "net_gross_profit": quantize_money(
            gross_sales_profit
            - total_profit_reversal
        ),
    }


def get_overview(
    db: Session,
    date_from: date | None,
    date_to: date | None,
    low_stock_threshold: int,
) -> dict[str, object]:
    """构造经营数据总览。"""

    validate_date_range(
        date_from=date_from,
        date_to=date_to,
    )

    return {
        "date_from": date_from,
        "date_to": date_to,
        "inventory": get_inventory_analytics(
            db=db,
            low_stock_threshold=(
                low_stock_threshold
            ),
        ),
        "sales": get_sales_analytics(
            db=db,
            date_from=date_from,
            date_to=date_to,
        ),
    }


def list_inventory_analytics(
    db: Session,
) -> list[dict[str, object]]:
    """查询全部 SKU 当前库存。"""

    return [
        build_inventory_item(
            sku=sku,
            inventory=inventory,
        )
        for sku, inventory in get_inventory_rows(db)
    ]


def list_low_stock_skus(
    db: Session,
    threshold: int,
) -> list[dict[str, object]]:
    """查询低库存 SKU。"""

    result: list[dict[str, object]] = []

    for sku, inventory in get_inventory_rows(db):
        item = build_inventory_item(
            sku=sku,
            inventory=inventory,
        )

        if (
            sku.status == SKUStatus.ACTIVE
            and int(item["available_qty"])
            <= threshold
        ):
            result.append(item)

    result.sort(
        key=lambda item: int(
            item["available_qty"]
        )
    )

    return result


def get_sku_performance(
    db: Session,
    date_from: date | None,
    date_to: date | None,
) -> list[dict[str, object]]:
    """按 SKU 汇总销售表现。"""

    validate_date_range(
        date_from=date_from,
        date_to=date_to,
    )

    performance: dict[int, dict[str, object]] = {}

    sales_statement = (
        select(SalesItem, SKU)
        .join(
            SalesOrder,
            SalesOrder.id
            == SalesItem.sales_order_id,
        )
        .join(
            SKU,
            SKU.id == SalesItem.sku_id,
        )
    )

    sales_statement = apply_date_range(
        statement=sales_statement,
        datetime_column=SalesOrder.sold_at,
        date_from=date_from,
        date_to=date_to,
    )

    sales_rows = list(
        db.execute(sales_statement).all()
    )

    for sales_item, sku in sales_rows:
        if sku.id not in performance:
            performance[sku.id] = {
                "local_sku": sku.local_sku,
                "barcode": sku.barcode,
                "brand": sku.brand,
                "article_number": (
                    sku.article_number
                ),
                "size": sku.size,
                "gross_units_sold": 0,
                "returned_or_reversed_units": 0,
                "gross_sales_amount": ZERO_MONEY,
                "deduction_amount": ZERO_MONEY,
                "gross_sales_cost": ZERO_MONEY,
                "deduction_cost": ZERO_MONEY,
            }

        item = performance[sku.id]

        item["gross_units_sold"] += (
            sales_item.quantity
        )

        item["gross_sales_amount"] += (
            sales_item.line_amount
        )

        item["gross_sales_cost"] += (
            sales_item.line_cost
        )

    return_statement = (
        select(ReturnItem, SKU)
        .join(
            ReturnOrder,
            ReturnOrder.id
            == ReturnItem.return_order_id,
        )
        .join(
            SKU,
            SKU.id == ReturnItem.sku_id,
        )
    )

    return_statement = apply_date_range(
        statement=return_statement,
        datetime_column=ReturnOrder.returned_at,
        date_from=date_from,
        date_to=date_to,
    )

    return_rows = list(
        db.execute(return_statement).all()
    )

    for return_item, sku in return_rows:
        if sku.id not in performance:
            performance[sku.id] = {
                "local_sku": sku.local_sku,
                "barcode": sku.barcode,
                "brand": sku.brand,
                "article_number": (
                    sku.article_number
                ),
                "size": sku.size,
                "gross_units_sold": 0,
                "returned_or_reversed_units": 0,
                "gross_sales_amount": ZERO_MONEY,
                "deduction_amount": ZERO_MONEY,
                "gross_sales_cost": ZERO_MONEY,
                "deduction_cost": ZERO_MONEY,
            }

        item = performance[sku.id]

        item["returned_or_reversed_units"] += (
            return_item.quantity
        )

        item["deduction_amount"] += (
            return_item.line_amount
        )

        item["deduction_cost"] += (
            return_item.line_cost
        )

    result: list[dict[str, object]] = []

    for item in performance.values():
        gross_units = int(
            item["gross_units_sold"]
        )

        deducted_units = int(
            item["returned_or_reversed_units"]
        )

        gross_amount = Decimal(
            item["gross_sales_amount"]
        )

        deduction_amount = Decimal(
            item["deduction_amount"]
        )

        gross_cost = Decimal(
            item["gross_sales_cost"]
        )

        deduction_cost = Decimal(
            item["deduction_cost"]
        )

        net_amount = (
            gross_amount
            - deduction_amount
        )

        net_cost = (
            gross_cost
            - deduction_cost
        )

        result.append(
            {
                **item,
                "net_units_sold": (
                    gross_units
                    - deducted_units
                ),
                "gross_sales_amount": (
                    quantize_money(gross_amount)
                ),
                "deduction_amount": (
                    quantize_money(
                        deduction_amount
                    )
                ),
                "net_sales_amount": (
                    quantize_money(net_amount)
                ),
                "gross_sales_cost": (
                    quantize_money(gross_cost)
                ),
                "deduction_cost": (
                    quantize_money(
                        deduction_cost
                    )
                ),
                "net_sales_cost": (
                    quantize_money(net_cost)
                ),
                "net_gross_profit": (
                    quantize_money(
                        net_amount
                        - net_cost
                    )
                ),
            }
        )

    result.sort(
        key=lambda item: Decimal(
            item["net_sales_amount"]
        ),
        reverse=True,
    )

    return result


def get_daily_sales(
    db: Session,
    date_from: date | None,
    date_to: date | None,
) -> list[dict[str, object]]:
    """按日期汇总销售、退货和冲销。"""

    validate_date_range(
        date_from=date_from,
        date_to=date_to,
    )

    daily_data: dict[
        date,
        dict[str, Decimal],
    ] = defaultdict(
        lambda: {
            "gross_sales_amount": ZERO_MONEY,
            "gross_sales_cost": ZERO_MONEY,
            "deduction_amount": ZERO_MONEY,
            "deduction_cost": ZERO_MONEY,
        }
    )

    sales_orders = get_sales_orders_in_range(
        db=db,
        date_from=date_from,
        date_to=date_to,
    )

    return_orders = get_return_orders_in_range(
        db=db,
        date_from=date_from,
        date_to=date_to,
    )

    for sales_order in sales_orders:
        business_date = (
            sales_order.sold_at.date()
        )

        daily_data[business_date][
            "gross_sales_amount"
        ] += sales_order.total_amount

        daily_data[business_date][
            "gross_sales_cost"
        ] += sales_order.total_cost

    for return_order in return_orders:
        business_date = (
            return_order.returned_at.date()
        )

        daily_data[business_date][
            "deduction_amount"
        ] += return_order.total_amount

        daily_data[business_date][
            "deduction_cost"
        ] += return_order.total_cost

    result: list[dict[str, object]] = []

    for business_date in sorted(
        daily_data.keys()
    ):
        item = daily_data[business_date]

        net_sales_amount = (
            item["gross_sales_amount"]
            - item["deduction_amount"]
        )

        net_sales_cost = (
            item["gross_sales_cost"]
            - item["deduction_cost"]
        )

        result.append(
            {
                "business_date": business_date,
                "gross_sales_amount": (
                    quantize_money(
                        item[
                            "gross_sales_amount"
                        ]
                    )
                ),
                "deduction_amount": (
                    quantize_money(
                        item["deduction_amount"]
                    )
                ),
                "net_sales_amount": (
                    quantize_money(
                        net_sales_amount
                    )
                ),
                "gross_sales_cost": (
                    quantize_money(
                        item["gross_sales_cost"]
                    )
                ),
                "deduction_cost": (
                    quantize_money(
                        item["deduction_cost"]
                    )
                ),
                "net_sales_cost": (
                    quantize_money(
                        net_sales_cost
                    )
                ),
                "net_gross_profit": (
                    quantize_money(
                        net_sales_amount
                        - net_sales_cost
                    )
                ),
            }
        )

    return result