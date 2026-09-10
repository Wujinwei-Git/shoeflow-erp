from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.db.session import get_db
from app.models.sales import SalesOrder
from app.schemas.returns import (
    ReturnCreate,
    ReturnRead,
    ReturnSummaryRead,
    SaleReverseCreate,
)
from app.services.returns_service import (
    build_return_data,
    create_customer_return,
    get_return_order,
    list_return_orders,
    reverse_sale,
)

router = APIRouter()


def serialize_return(
    db: Session,
    return_order: object,
) -> dict[str, object]:
    """序列化完整退货记录。"""

    return_data = build_return_data(
        db=db,
        return_order=return_order,
    )

    return (
        ReturnRead
        .model_validate(return_data)
        .model_dump(mode="json")
    )


@router.post(
    "/returns",
    status_code=status.HTTP_201_CREATED,
    summary="创建销售退货",
)
def create_return(
    payload: ReturnCreate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return_order = create_customer_return(
        db=db,
        payload=payload,
    )

    return success_response(
        data=serialize_return(
            db=db,
            return_order=return_order,
        ),
        message="销售退货成功",
    )


@router.get(
    "/returns",
    summary="查询最近退货和冲销记录",
)
def list_returns(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return_orders = list_return_orders(
        db=db,
        limit=limit,
    )

    result: list[dict[str, object]] = []

    for return_order in return_orders:
        statement = select(SalesOrder).where(
            SalesOrder.id
            == return_order.sales_order_id
        )

        sales_order = db.scalar(statement)

        summary = ReturnSummaryRead(
            return_no=return_order.return_no,
            sale_no=(
                sales_order.sale_no
                if sales_order is not None
                else ""
            ),
            return_type=return_order.return_type,
            total_amount=return_order.total_amount,
            total_cost=return_order.total_cost,
            gross_profit_reversal=(
                return_order.gross_profit_reversal
            ),
            returned_at=return_order.returned_at,
        )

        result.append(
            summary.model_dump(mode="json")
        )

    return success_response(
        data=result,
    )


@router.get(
    "/returns/{return_no}",
    summary="查询退货或冲销详情",
)
def get_return(
    return_no: str = Path(
        min_length=1,
        max_length=40,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return_order = get_return_order(
        db=db,
        return_no=return_no,
    )

    return success_response(
        data=serialize_return(
            db=db,
            return_order=return_order,
        ),
    )


@router.post(
    "/sales/{sale_no}/reverse",
    status_code=status.HTTP_201_CREATED,
    summary="整单冲销销售",
)
def reverse_sales_order(
    payload: SaleReverseCreate,
    sale_no: str = Path(
        min_length=1,
        max_length=40,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return_order = reverse_sale(
        db=db,
        sale_no=sale_no,
        payload=payload,
    )

    return success_response(
        data=serialize_return(
            db=db,
            return_order=return_order,
        ),
        message="销售冲销成功",
    )