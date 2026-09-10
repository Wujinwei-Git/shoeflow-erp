from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

WEB_DIR = Path(__file__).resolve().parent
INDEX_FILE = WEB_DIR / "templates" / "index.html"
INBOUND_FILE = WEB_DIR / "templates" / "inbound.html"
SALES_FILE = WEB_DIR / "templates" / "sales.html"
RETURNS_FILE = WEB_DIR / "templates" / "returns.html"
INVENTORY_CONTROL_FILE = WEB_DIR / "templates" / "inventory_control.html"
RECORDS_FILE = WEB_DIR / "templates" / "records.html"
SKU_CATALOG_FILE = WEB_DIR / "templates" / "sku_catalog.html"
@router.get(
    "/",
    include_in_schema=False,
)
def erp_home() -> FileResponse:
    """返回 ERP 操作首页。"""

    return FileResponse(INDEX_FILE)


@router.get(
    "/inbound",
    include_in_schema=False,
)
def inbound_page() -> FileResponse:
    """返回扫码入库页面。"""

    return FileResponse(INBOUND_FILE)


@router.get(
    "/sales",
    include_in_schema=False,
)
def sales_page() -> FileResponse:
    """返回销售出库页面。"""

    return FileResponse(SALES_FILE)

@router.get(
    "/returns",
    include_in_schema=False,
)
def returns_page() -> FileResponse:
    """返回退货与销售冲销页面。"""

    return FileResponse(RETURNS_FILE)


@router.get(
    "/inventory-control",
    include_in_schema=False,
)
def inventory_control_page() -> FileResponse:
    """返回库存校正与库存流水页面。"""

    return FileResponse(INVENTORY_CONTROL_FILE)

@router.get(
    "/records",
    include_in_schema=False,
)
def records_page() -> FileResponse:
    """返回销售与退货记录中心。"""

    return FileResponse(RECORDS_FILE)

@router.get(
    "/sku-catalog",
    include_in_schema=False,
)
def sku_catalog_page() -> FileResponse:
    """返回 SKU 商品档案管理页面。"""

    return FileResponse(SKU_CATALOG_FILE)