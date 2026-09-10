from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.models.sku import SKUStatus


class InventoryAnalytics(BaseModel):
    """库存汇总指标。"""

    sku_count: int
    active_sku_count: int

    on_hand_qty: int
    reserved_qty: int
    available_qty: int

    inventory_value: Decimal
    low_stock_sku_count: int


class SalesAnalytics(BaseModel):
    """销售经营汇总指标。"""

    sales_order_count: int
    return_order_count: int
    reversal_order_count: int

    gross_units_sold: int
    returned_units: int
    reversed_units: int
    net_units_sold: int

    gross_sales_amount: Decimal
    gross_sales_cost: Decimal
    gross_sales_profit: Decimal

    return_amount: Decimal
    return_cost: Decimal
    return_profit_reversal: Decimal

    reversal_amount: Decimal
    reversal_cost: Decimal
    reversal_profit: Decimal

    net_sales_amount: Decimal
    net_sales_cost: Decimal
    net_gross_profit: Decimal


class AnalyticsOverview(BaseModel):
    """经营数据总览。"""

    date_from: date | None
    date_to: date | None

    inventory: InventoryAnalytics
    sales: SalesAnalytics


class InventoryItemAnalytics(BaseModel):
    """单个 SKU 库存统计。"""

    local_sku: str
    barcode: str | None
    brand: str
    article_number: str
    size: str
    status: SKUStatus

 

    on_hand_qty: int
    reserved_qty: int
    available_qty: int

    avg_cost: Decimal
    inventory_value: Decimal


class SKUPerformanceAnalytics(BaseModel):
    """按 SKU 统计销售表现。"""

    local_sku: str
    barcode: str | None
    brand: str
    article_number: str
    size: str

    gross_units_sold: int
    returned_or_reversed_units: int
    net_units_sold: int

    gross_sales_amount: Decimal
    deduction_amount: Decimal
    net_sales_amount: Decimal

    gross_sales_cost: Decimal
    deduction_cost: Decimal
    net_sales_cost: Decimal

    net_gross_profit: Decimal


class DailySalesAnalytics(BaseModel):
    """按日期统计经营数据。"""

    business_date: date

    gross_sales_amount: Decimal
    deduction_amount: Decimal
    net_sales_amount: Decimal

    gross_sales_cost: Decimal
    deduction_cost: Decimal
    net_sales_cost: Decimal

    net_gross_profit: Decimal