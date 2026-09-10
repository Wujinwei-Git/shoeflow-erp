from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.db.session import get_db
from app.schemas.analytics import (
    AnalyticsOverview,
    DailySalesAnalytics,
    InventoryItemAnalytics,
    SKUPerformanceAnalytics,
)
from app.services.analytics_service import (
    get_daily_sales,
    get_overview,
    get_sku_performance,
    list_inventory_analytics,
    list_low_stock_skus,
)

router = APIRouter(
    prefix="/analytics",
)


@router.get(
    "/overview",
    summary="查询经营数据总览",
)
def overview(
    date_from: date | None = Query(
        default=None,
    ),
    date_to: date | None = Query(
        default=None,
    ),
    low_stock_threshold: int = Query(
        default=2,
        ge=0,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    data = get_overview(
        db=db,
        date_from=date_from,
        date_to=date_to,
        low_stock_threshold=(
            low_stock_threshold
        ),
    )

    serialized_data = (
        AnalyticsOverview
        .model_validate(data)
        .model_dump(mode="json")
    )

    return success_response(
        data=serialized_data,
    )


@router.get(
    "/inventory",
    summary="查询全部SKU库存统计",
)
def inventory_analytics(
    db: Session = Depends(get_db),
) -> dict[str, object]:
    data = list_inventory_analytics(
        db=db,
    )

    serialized_data = [
        InventoryItemAnalytics
        .model_validate(item)
        .model_dump(mode="json")
        for item in data
    ]

    return success_response(
        data=serialized_data,
    )


@router.get(
    "/low-stock",
    summary="查询低库存SKU",
)
def low_stock(
    threshold: int = Query(
        default=2,
        ge=0,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    data = list_low_stock_skus(
        db=db,
        threshold=threshold,
    )

    serialized_data = [
        InventoryItemAnalytics
        .model_validate(item)
        .model_dump(mode="json")
        for item in data
    ]

    return success_response(
        data=serialized_data,
    )


@router.get(
    "/sales-by-sku",
    summary="按SKU查询销售表现",
)
def sales_by_sku(
    date_from: date | None = Query(
        default=None,
    ),
    date_to: date | None = Query(
        default=None,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    data = get_sku_performance(
        db=db,
        date_from=date_from,
        date_to=date_to,
    )

    serialized_data = [
        SKUPerformanceAnalytics
        .model_validate(item)
        .model_dump(mode="json")
        for item in data
    ]

    return success_response(
        data=serialized_data,
    )


@router.get(
    "/daily-sales",
    summary="按日期查询销售趋势",
)
def daily_sales(
    date_from: date | None = Query(
        default=None,
    ),
    date_to: date | None = Query(
        default=None,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    data = get_daily_sales(
        db=db,
        date_from=date_from,
        date_to=date_to,
    )

    serialized_data = [
        DailySalesAnalytics
        .model_validate(item)
        .model_dump(mode="json")
        for item in data
    ]

    return success_response(
        data=serialized_data,
    )