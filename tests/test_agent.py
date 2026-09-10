import json
from typing import Any

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User, UserRole
from app.services.deepseek_service import (
    AgentModelReply,
    AgentModelToolCall,
    get_agent_model_client,
)


client = TestClient(app)

TEST_USERNAME = "agentadmin"
TEST_PASSWORD = "StrongPass123!"


class FakeInventoryModelClient:
    """先调用库存工具，再根据结果生成自然语言答案。"""

    def __init__(self) -> None:
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
                        id="call_inventory_1",
                        name="query_inventory",
                        arguments=json.dumps(
                            {
                                "article_number": (
                                    "DD1391-100"
                                ),
                                "size": "42",
                            }
                        ),
                    )
                ]
            )

        tool_message = messages[-1]
        assert tool_message["role"] == "tool"

        tool_result = json.loads(
            tool_message["content"]
        )
        item = tool_result["data"]["items"][0]

        return AgentModelReply(
            content=(
                f"NIKE {item['article_number']} "
                f"{item['size']} 当前库存 "
                f"{item['on_hand_qty']} 双。"
            )
        )


class FakeTextModelClient:
    """不调用工具的普通文字回复模型。"""

    def __init__(self) -> None:
        self.offered_tool_names: list[str] = []

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AgentModelReply:
        self.offered_tool_names = [
            item["function"]["name"]
            for item in tools
        ]

        return AgentModelReply(
            content="你好，我可以帮你查询 SKU 和库存。"
        )


class FakeMalformedArgumentsModelClient:
    """模拟模型生成损坏的工具参数。"""

    def __init__(self) -> None:
        self.call_count = 0

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AgentModelReply:
        self.call_count += 1

        if self.call_count == 1:
            return AgentModelReply(
                tool_calls=[
                    AgentModelToolCall(
                        id="call_invalid_1",
                        name="query_inventory",
                        arguments="{invalid json",
                    )
                ]
            )

        tool_result = json.loads(
            messages[-1]["content"]
        )
        assert tool_result["ok"] is False

        return AgentModelReply(
            content="查询条件解析失败，请重新描述。"
        )


class FakeUnauthorizedWriteModelClient:
    """模拟模型擅自请求一个未授权的写工具。"""

    def __init__(self) -> None:
        self.call_count = 0

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AgentModelReply:
        self.call_count += 1

        if self.call_count == 1:
            return AgentModelReply(
                tool_calls=[
                    AgentModelToolCall(
                        id="call_write_1",
                        name="delete_inventory",
                        arguments="{}",
                    )
                ]
            )

        tool_result = json.loads(
            messages[-1]["content"]
        )
        assert tool_result["ok"] is False

        return AgentModelReply(
            content="该操作未获授权，当前不能执行。"
        )


def create_test_user_and_login() -> str:
    with SessionLocal() as db:
        user = User(
            username=TEST_USERNAME,
            password_hash=hash_password(
                TEST_PASSWORD
            ),
            display_name="Agent 测试管理员",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(user)
        db.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def create_inventory_fixture() -> str:
    sku_response = client.post(
        "/api/v1/skus",
        json={
            "barcode": "6900000099001",
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


def test_agent_inventory_query_uses_real_data() -> None:
    token = create_test_user_and_login()
    local_sku = create_inventory_fixture()
    fake_model = FakeInventoryModelClient()

    app.dependency_overrides[
        get_agent_model_client
    ] = lambda: fake_model

    try:
        response = client.post(
            "/api/v1/agent/chat",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "message": (
                    "查询货号 DD1391-100 42 码的库存"
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
    assert "当前库存 6 双" in data["reply"]
    assert data["tools_used"] == [
        "query_inventory"
    ]

    tool_data = data["tool_results"][0]["data"]
    inventory = tool_data["data"]["items"][0]

    assert inventory["local_sku"] == local_sku
    assert inventory["size"] == "EUR 42"
    assert inventory["on_hand_qty"] == 6
    assert inventory["avg_cost"] == "500.00"

    inventory_response = client.get(
        f"/api/v1/inventory/{local_sku}"
    )
    assert inventory_response.status_code == 200
    assert (
        inventory_response
        .json()["data"]["on_hand_qty"]
        == 6
    )


def test_agent_requires_login() -> None:
    fake_model = FakeTextModelClient()
    app.dependency_overrides[
        get_agent_model_client
    ] = lambda: fake_model

    try:
        response = client.post(
            "/api/v1/agent/chat",
            json={
                "message": "查询库存",
            },
        )
    finally:
        app.dependency_overrides.pop(
            get_agent_model_client,
            None,
        )

    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_agent_only_offers_query_and_preview_tools() -> None:
    token = create_test_user_and_login()
    fake_model = FakeTextModelClient()
    app.dependency_overrides[
        get_agent_model_client
    ] = lambda: fake_model

    try:
        response = client.post(
            "/api/v1/agent/chat",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "message": "你好",
            },
        )
    finally:
        app.dependency_overrides.pop(
            get_agent_model_client,
            None,
        )

    assert response.status_code == 200
    assert set(fake_model.offered_tool_names) == {
        "search_skus",
        "query_inventory",
        "preview_sale",
    }
    assert "confirm_sale" not in fake_model.offered_tool_names
    assert "create_sale" not in fake_model.offered_tool_names
    assert "adjust_inventory" not in fake_model.offered_tool_names


def test_agent_rejects_blank_message() -> None:
    token = create_test_user_and_login()
    fake_model = FakeTextModelClient()
    app.dependency_overrides[
        get_agent_model_client
    ] = lambda: fake_model

    try:
        response = client.post(
            "/api/v1/agent/chat",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "message": "   ",
            },
        )
    finally:
        app.dependency_overrides.pop(
            get_agent_model_client,
            None,
        )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_agent_never_turns_malformed_arguments_into_query_all() -> None:
    token = create_test_user_and_login()
    fake_model = FakeMalformedArgumentsModelClient()
    app.dependency_overrides[
        get_agent_model_client
    ] = lambda: fake_model

    try:
        response = client.post(
            "/api/v1/agent/chat",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "message": "查询这个货号的库存",
            },
        )
    finally:
        app.dependency_overrides.pop(
            get_agent_model_client,
            None,
        )

    assert response.status_code == 200

    tool_result = response.json()["data"][
        "tool_results"
    ][0]["data"]

    assert tool_result["ok"] is False
    assert (
        tool_result["error"]["code"]
        == "INVALID_TOOL_ARGUMENTS"
    )


def test_agent_blocks_unlisted_write_tool() -> None:
    token = create_test_user_and_login()
    fake_model = FakeUnauthorizedWriteModelClient()
    app.dependency_overrides[
        get_agent_model_client
    ] = lambda: fake_model

    try:
        response = client.post(
            "/api/v1/agent/chat",
            headers={
                "Authorization": f"Bearer {token}",
            },
            json={
                "message": "删除库存",
            },
        )
    finally:
        app.dependency_overrides.pop(
            get_agent_model_client,
            None,
        )

    assert response.status_code == 200

    tool_result = response.json()["data"][
        "tool_results"
    ][0]["data"]

    assert tool_result["ok"] is False
    assert (
        tool_result["error"]["code"]
        == "TOOL_NOT_ALLOWED"
    )
