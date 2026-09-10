from fastapi import APIRouter

from app.core.config import settings
from app.core.responses import success_response

router = APIRouter()


@router.get(
    "/health",
    summary="服务健康检查",
    description="检查 ShoeFlow ERP API 进程是否正常运行。",
)
def health_check() -> dict[str, object]:
    return success_response(
        data={
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "status": "healthy",
        }
    )

