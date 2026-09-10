from fastapi import (
    APIRouter,
    Depends,
    Path,
    status,
)
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.db.session import get_db
from app.schemas.sku import (
    SKUCreate,
    SKURead,
    SKUStatusUpdate,
)
from app.services.sku_service import (
    create_sku,
    get_sku_by_barcode,
    get_sku_by_local_sku,
    list_skus,
    update_sku_status,
)

router = APIRouter(
    prefix="/skus",
)


def serialize_sku(sku: object) -> dict[str, object]:
    """将数据库 SKU 转换成接口返回结构。"""

    return (
        SKURead
        .model_validate(sku)
        .model_dump(mode="json")
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="创建 SKU",
)
def create(
    payload: SKUCreate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    sku = create_sku(
        db=db,
        payload=payload,
    )

    return success_response(
        data=serialize_sku(sku),
        message="SKU 创建成功",
    )


@router.get(
    "/barcode/{barcode}",
    summary="按鞋盒条码查询 SKU",
)
def get_by_barcode(
    barcode: str = Path(
        min_length=1,
        max_length=64,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    sku = get_sku_by_barcode(
        db=db,
        barcode=barcode,
    )

    return success_response(
        data=serialize_sku(sku),
    )


@router.get(
    "",
    summary="查询全部 SKU",
)
def get_all_skus(
    db: Session = Depends(get_db),
) -> dict[str, object]:
    skus = list_skus(db=db)

    return success_response(
        data=[
            serialize_sku(sku)
            for sku in skus
        ],
    )

@router.get(
    "/{local_sku}",
    summary="按内部编码查询 SKU",
)
def get_by_local_sku(
    local_sku: str = Path(
        min_length=1,
        max_length=32,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    sku = get_sku_by_local_sku(
        db=db,
        local_sku=local_sku,
    )

    return success_response(
        data=serialize_sku(sku),
    )




@router.put(
    "/{local_sku}/status",
    summary="修改 SKU 状态",
)
def update_status(
    payload: SKUStatusUpdate,
    local_sku: str = Path(
        min_length=1,
        max_length=32,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    sku = get_sku_by_local_sku(
        db=db,
        local_sku=local_sku,
    )

    updated_sku = update_sku_status(
        db=db,
        sku=sku,
        new_status=payload.status,
    )

    return success_response(
        data=serialize_sku(updated_sku),
        message="状态修改成功",
    )