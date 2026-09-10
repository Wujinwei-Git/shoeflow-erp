from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.db.session import get_db
from app.schemas.sales import (
    SaleCreate,
    SaleRead,
    SaleSummaryRead,
)
from app.services.sales_service import (
    build_sale_data,
    create_sale,
    get_sales_order,
    list_sales_orders,
)

router = APIRouter(
    prefix="/sales",
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="创建销售单并扣减库存",
)
def create(
    payload: SaleCreate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    sales_order = create_sale(
        db=db,
        payload=payload,
    )

    sale_data = build_sale_data(
        db=db,
        sales_order=sales_order,
    )

    serialized_data = (
        SaleRead
        .model_validate(sale_data)
        .model_dump(mode="json")
    )

    return success_response(
        data=serialized_data,
        message="销售出库成功",
    )


@router.get(
    "",
    summary="查询最近销售记录",
)
def list_sales(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    sales_orders = list_sales_orders(
        db=db,
        limit=limit,
    )

    serialized_data = [
        SaleSummaryRead(
            sale_no=sales_order.sale_no,
            status=sales_order.status,
            total_amount=sales_order.total_amount,
            total_cost=sales_order.total_cost,
            gross_profit=sales_order.gross_profit,
            sold_at=sales_order.sold_at,
        ).model_dump(mode="json")
        for sales_order in sales_orders
    ]

    return success_response(
        data=serialized_data,
    )


@router.get(
    "/{sale_no}",
    summary="查询销售单详情",
)
def get_sale(
    sale_no: str = Path(
        min_length=1,
        max_length=40,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    sales_order = get_sales_order(
        db=db,
        sale_no=sale_no,
    )

    sale_data = build_sale_data(
        db=db,
        sales_order=sales_order,
    )

    serialized_data = (
        SaleRead
        .model_validate(sale_data)
        .model_dump(mode="json")
    )

    return success_response(
        data=serialized_data,
    )