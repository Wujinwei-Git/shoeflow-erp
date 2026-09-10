import json
from datetime import timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.agent import AgentAction, AgentActionStatus
from app.models.user import User, UserRole
from app.services.agent_action_service import utc_now
from app.services.deepseek_service import (
    AgentModelReply,
    AgentModelToolCall,
    get_agent_model_client,
)


client = TestClient(app)

TEST_PASSWORD = "StrongPass123!"


class FakeSalePreviewModelClient:
    """模拟 DeepSeek 生成销售预览调用，再解释工具结果。"""

    def __init__(
        self,
        *,
        quantity: int = 2,
        unit_price: str = "800.00",
    ) -> None:
        self.quantity = quantity
        self.unit_price = unit_price
        self.call_count = 0
        self.offered_tool_names: list[str] = []

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AgentModelReply:
        self.call_count += 1
        self.offered_tool_names = [
            item["function"]["name"]
            for item in tools
        ]

        if self.call_count == 1:
            return AgentModelReply(
                tool_calls=[
                    AgentModelToolCall(
                        id="call_sale_preview_1",
                        name="preview_sale",
                        arguments=json.dumps(
                            {
                                "article_number": (
                                    "DD1391-100"
                                ),
                                "size": "42",
                                "quantity": self.quantity,
                                "unit_price": self.unit_price,
                                "note": "Agent 测试销售",
                            }
                        ),
                    )
                ]
            )

        tool_result = json.loads(
            messages[-1]["content"]
        )

        if tool_result["ok"]:
            preview = tool_result["data"][
                "pending_action"
            ]["preview"]
            return AgentModelReply(
                content=(
                    "已生成待确认销售预览："
                    f"销售额 {preview['total_amount']} 元，"
                    f"预计毛利润 {preview['gross_profit']} 元。"
                    "请核对后点击确认。"
                )
            )

        return AgentModelReply(
            content=tool_result["error"]["message"]
        )


def create_user_and_login(
    username: str,
) -> str:
    with SessionLocal() as db:
        user = User(
            username=username,
            password_hash=hash_password(
                TEST_PASSWORD
            ),
            display_name=f"{username} 测试用户",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(user)
        db.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
    }


def create_inventory_fixture() -> str:
    sku_response = client.post(
        "/api/v1/skus",
        json={
            "barcode": "6900000088001",
            "brand": "Nike",
            "article_number": "DD1391-100",
            "size": "EUR 42",
            "status": "active",
        },
    )
    assert sku_response.status_code == 201

    local_sku = sku_response.json()["data"][
        "local_sku"
    ]

    inbound_response = client.post(
        "/api/v1/inventory/inbounds",
        json={
            "local_sku": local_sku,
            "quantity": 6,
            "unit_cost": "500.00",
        },
    )
    assert inbound_response.status_code == 201

    return local_sku


def create_sale_preview(
    token: str,
    *,
    quantity: int = 2,
    unit_price: str = "800.00",
) -> dict[str, Any]:
    fake_model = FakeSalePreviewModelClient(
        quantity=quantity,
        unit_price=unit_price,
    )
    app.dependency_overrides[
        get_agent_model_client
    ] = lambda: fake_model

    try:
        response = client.post(
            "/api/v1/agent/chat",
            headers=auth_headers(token),
            json={
                "message": (
                    "今天卖出货号 DD1391-100 的 42 码"
                    f" {quantity} 双，每双 {unit_price} 元"
                ),
            },
        )
    finally:
        app.dependency_overrides.pop(
            get_agent_model_client,
            None,
        )

    assert response.status_code == 200
    data = response.json()["data"]
    data["_offered_tool_names"] = (
        fake_model.offered_tool_names
    )
    return data


def get_on_hand_qty(local_sku: str) -> int:
    response = client.get(
        f"/api/v1/inventory/{local_sku}"
    )
    assert response.status_code == 200
    return response.json()["data"]["on_hand_qty"]


def test_sale_preview_calculates_profit_without_writing() -> None:
    token = create_user_and_login("previewowner")
    local_sku = create_inventory_fixture()

    data = create_sale_preview(token)

    assert data["tools_used"] == ["preview_sale"]
    assert set(data["_offered_tool_names"]) == {
        "search_skus",
        "query_inventory",
        "preview_sale",
    }

    action = data["pending_action"]
    assert action["status"] == "pending"
    assert action["requires_confirmation"] is True

    preview = action["preview"]
    assert preview["total_quantity"] == 2
    assert preview["total_amount"] == "1600.00"
    assert preview["total_cost"] == "1000.00"
    assert preview["gross_profit"] == "600.00"
    assert preview["items"][0]["after_on_hand_qty"] == 4

    assert get_on_hand_qty(local_sku) == 6
    assert client.get("/api/v1/sales").json()["data"] == []


def test_confirm_sale_is_atomic_and_idempotent() -> None:
    token = create_user_and_login("confirmowner")
    local_sku = create_inventory_fixture()
    action_id = create_sale_preview(token)[
        "pending_action"
    ]["action_id"]

    first_response = client.post(
        f"/api/v1/agent/actions/{action_id}/confirm",
        headers=auth_headers(token),
    )

    assert first_response.status_code == 200
    first_body = first_response.json()
    assert first_body["data"]["status"] == "confirmed"
    assert first_body["data"]["requires_confirmation"] is False

    sale = first_body["data"]["result"]["sale"]
    assert sale["total_amount"] == "1600.00"
    assert sale["total_cost"] == "1000.00"
    assert sale["gross_profit"] == "600.00"
    assert get_on_hand_qty(local_sku) == 4

    second_response = client.post(
        f"/api/v1/agent/actions/{action_id}/confirm",
        headers=auth_headers(token),
    )

    assert second_response.status_code == 200
    second_body = second_response.json()
    assert "未重复扣减库存" in second_body["message"]
    assert (
        second_body["data"]["result"]["sale"]["sale_no"]
        == sale["sale_no"]
    )
    assert get_on_hand_qty(local_sku) == 4

    sales = client.get("/api/v1/sales").json()["data"]
    assert len(sales) == 1

    movements = client.get(
        f"/api/v1/inventory/{local_sku}/movements"
    ).json()["data"]
    assert len(
        [
            item
            for item in movements
            if item["movement_type"] == "sale"
        ]
    ) == 1


def test_cancelled_preview_cannot_be_confirmed() -> None:
    token = create_user_and_login("cancelowner")
    local_sku = create_inventory_fixture()
    action_id = create_sale_preview(token)[
        "pending_action"
    ]["action_id"]

    cancel_response = client.post(
        f"/api/v1/agent/actions/{action_id}/cancel",
        headers=auth_headers(token),
    )

    assert cancel_response.status_code == 200
    assert cancel_response.json()["data"]["status"] == "cancelled"

    confirm_response = client.post(
        f"/api/v1/agent/actions/{action_id}/confirm",
        headers=auth_headers(token),
    )

    assert confirm_response.status_code == 409
    assert (
        confirm_response.json()["code"]
        == "AGENT_ACTION_CANCELLED"
    )
    assert get_on_hand_qty(local_sku) == 6


def test_action_is_private_to_the_creating_user() -> None:
    owner_token = create_user_and_login("privateowner")
    other_token = create_user_and_login("otheradmin")
    local_sku = create_inventory_fixture()
    action_id = create_sale_preview(owner_token)[
        "pending_action"
    ]["action_id"]

    get_response = client.get(
        f"/api/v1/agent/actions/{action_id}",
        headers=auth_headers(other_token),
    )
    confirm_response = client.post(
        f"/api/v1/agent/actions/{action_id}/confirm",
        headers=auth_headers(other_token),
    )

    assert get_response.status_code == 404
    assert confirm_response.status_code == 404
    assert get_on_hand_qty(local_sku) == 6


def test_expired_preview_is_rejected_without_stock_change() -> None:
    token = create_user_and_login("expiredowner")
    local_sku = create_inventory_fixture()
    action_id = create_sale_preview(token)[
        "pending_action"
    ]["action_id"]

    with SessionLocal() as db:
        action = db.get(AgentAction, action_id)
        assert action is not None
        action.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()

    confirm_response = client.post(
        f"/api/v1/agent/actions/{action_id}/confirm",
        headers=auth_headers(token),
    )

    assert confirm_response.status_code == 409
    assert (
        confirm_response.json()["code"]
        == "AGENT_ACTION_EXPIRED"
    )
    assert get_on_hand_qty(local_sku) == 6

    status_response = client.get(
        f"/api/v1/agent/actions/{action_id}",
        headers=auth_headers(token),
    )
    assert status_response.json()["data"]["status"] == "expired"


def test_changed_inventory_invalidates_old_preview() -> None:
    token = create_user_and_login("staleowner")
    local_sku = create_inventory_fixture()
    action_id = create_sale_preview(token)[
        "pending_action"
    ]["action_id"]

    inbound_response = client.post(
        "/api/v1/inventory/inbounds",
        json={
            "local_sku": local_sku,
            "quantity": 1,
            "unit_cost": "600.00",
        },
    )
    assert inbound_response.status_code == 201

    confirm_response = client.post(
        f"/api/v1/agent/actions/{action_id}/confirm",
        headers=auth_headers(token),
    )

    assert confirm_response.status_code == 409
    assert (
        confirm_response.json()["code"]
        == "AGENT_PREVIEW_STALE"
    )
    assert get_on_hand_qty(local_sku) == 7
    assert client.get("/api/v1/sales").json()["data"] == []

    status_response = client.get(
        f"/api/v1/agent/actions/{action_id}",
        headers=auth_headers(token),
    )
    action = status_response.json()["data"]
    assert action["status"] == "failed"
    assert action["error"]["code"] == "AGENT_PREVIEW_STALE"


def test_insufficient_stock_does_not_create_pending_action() -> None:
    token = create_user_and_login("shortstockowner")
    local_sku = create_inventory_fixture()

    data = create_sale_preview(
        token,
        quantity=7,
    )

    assert data["pending_action"] is None
    tool_result = data["tool_results"][0]["data"]
    assert tool_result["ok"] is False
    assert (
        tool_result["error"]["code"]
        == "INSUFFICIENT_STOCK"
    )
    assert get_on_hand_qty(local_sku) == 6

    with SessionLocal() as db:
        actions = list(
            db.scalars(select(AgentAction)).all()
        )
    assert actions == []


def test_action_endpoints_require_login() -> None:
    response = client.post(
        "/api/v1/agent/actions/00000000-0000-0000-0000-000000000000/confirm"
    )

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_agent_action_status_values_are_stable() -> None:
    assert {item.value for item in AgentActionStatus} == {
        "pending",
        "confirmed",
        "cancelled",
        "expired",
        "failed",
    }
