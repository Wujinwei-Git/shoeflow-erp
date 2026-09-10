from fastapi import APIRouter

from app.api.v1.routes.agent import router as agent_router
from app.api.v1.routes.analytics import router as analytics_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.corrections import router as corrections_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.inventory import router as inventory_router
from app.api.v1.routes.returns import router as returns_router
from app.api.v1.routes.sales import router as sales_router
from app.api.v1.routes.skus import router as skus_router


api_router = APIRouter()

api_router.include_router(
    health_router,
    tags=["系统"],
)

api_router.include_router(
    auth_router,
    tags=["账号认证"],
)

api_router.include_router(
    agent_router,
    tags=["AI 经营助手"],
)

api_router.include_router(
    skus_router,
    tags=["SKU 主数据"],
)

api_router.include_router(
    corrections_router,
    tags=["库存校正"],
)

api_router.include_router(
    inventory_router,
    tags=["库存管理"],
)

api_router.include_router(
    sales_router,
    tags=["销售管理"],
)

api_router.include_router(
    returns_router,
    tags=["退货与冲销"],
)

api_router.include_router(
    analytics_router,
    tags=["经营统计"],
)
