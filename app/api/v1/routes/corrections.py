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
from app.schemas.corrections import (
    InventoryCorrectionCreate,
    InventoryCorrectionRead,
)
from app.services.corrections_service import (
    build_correction_data,
    create_inventory_correction,
    get_correction,
    list_corrections,
)

router = APIRouter(
    prefix="/inventory/corrections",
)


def serialize_correction(
    db: Session,
    correction: object,
) -> dict[str, object]:
    """序列化库存校正记录。"""

    correction_data = build_correction_data(
        db=db,
        correction=correction,
    )

    return (
        InventoryCorrectionRead
        .model_validate(correction_data)
        .model_dump(mode="json")
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="手动增加或减少库存",
)
def create(
    payload: InventoryCorrectionCreate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    correction = create_inventory_correction(
        db=db,
        payload=payload,
    )

    return success_response(
        data=serialize_correction(
            db=db,
            correction=correction,
        ),
        message="库存数量校正成功",
    )


@router.get(
    "",
    summary="查询最近库存校正记录",
)
def list_inventory_corrections(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    corrections = list_corrections(
        db=db,
        limit=limit,
    )

    result = [
        serialize_correction(
            db=db,
            correction=correction,
        )
        for correction in corrections
    ]

    return success_response(
        data=result,
    )


@router.get(
    "/{correction_no}",
    summary="查询库存校正详情",
)
def get_inventory_correction(
    correction_no: str = Path(
        min_length=1,
        max_length=40,
    ),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    correction = get_correction(
        db=db,
        correction_no=correction_no,
    )

    return success_response(
        data=serialize_correction(
            db=db,
            correction=correction,
        ),
    )