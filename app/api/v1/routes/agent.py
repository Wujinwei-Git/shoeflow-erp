from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.responses import success_response
from app.db.session import get_db
from app.models.user import User
from app.schemas.agent import AgentChatRequest
from app.services.agent_action_service import (
    cancel_agent_action,
    confirm_agent_action,
    get_agent_action,
    serialize_agent_action,
)
from app.services.agent_service import run_agent
from app.services.deepseek_service import (
    AgentModelClient,
    get_agent_model_client,
)


router = APIRouter(
    prefix="/agent",
)


@router.post(
    "/chat",
    summary="与 ShoeFlow AI 经营助手对话",
)
def chat_with_agent(
    payload: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    model_client: AgentModelClient = Depends(
        get_agent_model_client
    ),
) -> dict[str, object]:
    result = run_agent(
        db=db,
        user_message=payload.message,
        current_user=current_user,
        model_client=model_client,
    )

    return success_response(
        data=result.model_dump(mode="json"),
        message="AI 助手回复成功",
    )


@router.get(
    "/actions/{action_id}",
    summary="查询自己的 Agent 待确认操作",
)
def read_agent_action(
    action_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    action = get_agent_action(
        db=db,
        action_id=str(action_id),
        current_user=current_user,
    )

    return success_response(
        data=serialize_agent_action(action),
        message="待确认操作查询成功",
    )


@router.post(
    "/actions/{action_id}/confirm",
    summary="确认并执行自己的 Agent 操作",
)
def confirm_action(
    action_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    action, executed = confirm_agent_action(
        db=db,
        action_id=str(action_id),
        current_user=current_user,
    )

    return success_response(
        data=serialize_agent_action(action),
        message=(
            "销售确认成功，库存已扣减"
            if executed
            else "该销售已经确认，本次未重复扣减库存"
        ),
    )


@router.post(
    "/actions/{action_id}/cancel",
    summary="取消自己的 Agent 待确认操作",
)
def cancel_action(
    action_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    action, cancelled = cancel_agent_action(
        db=db,
        action_id=str(action_id),
        current_user=current_user,
    )

    return success_response(
        data=serialize_agent_action(action),
        message=(
            "待确认操作已取消"
            if cancelled
            else "该操作此前已经取消"
        ),
    )
