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
from app.services.rag_service import (
    execute_knowledge_tool,
    search_knowledge,
)


client = TestClient(app)


class FakeRagModelClient:
    """先检索操作手册，再使用检索内容回答。"""

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
                        id="call_rag_1",
                        name="search_erp_manual",
                        arguments=json.dumps(
                            {
                                "query": (
                                    "第一次扫描新条码"
                                    "怎么建立商品档案"
                                ),
                                "limit": 2,
                            },
                            ensure_ascii=False,
                        ),
                    )
                ]
            )

        tool_message = messages[-1]
        assert tool_message["role"] == "tool"
        tool_result = json.loads(
            tool_message["content"]
        )
        first_source = tool_result["data"][
            "items"
        ][0]

        return AgentModelReply(
            content=(
                "第一次扫描时填写品牌、货号和尺码创建 SKU。\n"
                f"来源：{first_source['document_title']} > "
                f"{first_source['section_title']}"
            )
        )


def create_test_user_and_login() -> str:
    with SessionLocal() as db:
        user = User(
            username="ragadmin",
            password_hash=hash_password(
                "StrongPass123!"
            ),
            display_name="RAG 测试管理员",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(user)
        db.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": "ragadmin",
            "password": "StrongPass123!",
        },
    )

    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def test_rag_finds_first_scan_instructions() -> None:
    result = search_knowledge(
        "第一次扫描新条码为什么没有商品信息，怎么建档？",
        limit=3,
    )

    assert result["count"] == 3
    first_item = result["items"][0]
    assert first_item["document_title"] == (
        "SKU 商品档案操作手册"
    )
    assert first_item["section_title"] == (
        "第一次扫描新条码"
    )
    assert "品牌、货号和尺码" in first_item["content"]


def test_rag_prioritizes_return_correction_difference() -> None:
    result = search_knowledge(
        "顾客退货和库存校正有什么区别？",
        limit=3,
    )

    assert result["count"] == 3
    sections = [
        item["section_title"]
        for item in result["items"]
    ]
    assert "退货与库存校正的区别" in sections[:2]


def test_rag_returns_no_result_for_unrelated_question() -> None:
    result = search_knowledge(
        "火星轨道力学与恒星光谱分类",
        limit=3,
    )

    assert result["count"] == 0
    assert result["items"] == []


def test_rag_tool_rejects_invalid_arguments() -> None:
    result = execute_knowledge_tool(
        raw_arguments={
            "query": "   ",
            "unknown": True,
        }
    )

    assert result["ok"] is False
    assert result["error"]["code"] == (
        "INVALID_KNOWLEDGE_QUERY"
    )


def test_agent_returns_structured_knowledge_sources() -> None:
    token = create_test_user_and_login()
    fake_model = FakeRagModelClient()
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
                    "第一次扫描新条码时怎么建立商品档案？"
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
    assert data["tools_used"] == [
        "search_erp_manual"
    ]
    assert len(data["sources"]) == 2
    assert data["sources"][0]["document_title"] == (
        "SKU 商品档案操作手册"
    )
    assert "来源：" in data["reply"]
    assert data["pending_action"] is None
