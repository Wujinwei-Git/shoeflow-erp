from dataclasses import dataclass, field
from typing import Any, Protocol

from fastapi import status
from openai import OpenAI, OpenAIError

from app.core.config import settings
from app.core.exceptions import AppException


@dataclass(frozen=True)
class AgentModelToolCall:
    """模型返回的一次工具调用。"""

    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class AgentModelReply:
    """与具体模型 SDK 解耦的统一回复。"""

    content: str | None = None
    tool_calls: list[AgentModelToolCall] = field(
        default_factory=list,
    )

    def as_assistant_message(self) -> dict[str, Any]:
        message: dict[str, Any] = {
            "role": "assistant",
            "content": self.content,
        }

        if self.tool_calls:
            message["tool_calls"] = [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": tool_call.arguments,
                    },
                }
                for tool_call in self.tool_calls
            ]

        return message


class AgentModelClient(Protocol):
    """Agent 模型客户端协议，便于测试时替换为假模型。"""

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AgentModelReply:
        ...


class DeepSeekAgentClient:
    """DeepSeek OpenAI 兼容接口客户端。"""

    def __init__(self) -> None:
        secret = settings.deepseek_api_key
        api_key = (
            secret.get_secret_value().strip()
            if secret is not None
            else ""
        )

        if not api_key:
            raise AppException(
                message="AI 助手尚未配置 DeepSeek API Key",
                code="AGENT_NOT_CONFIGURED",
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
            )

        self.client = OpenAI(
            api_key=api_key,
            base_url=settings.deepseek_base_url,
            timeout=settings.deepseek_timeout_seconds,
        )

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AgentModelReply:
        try:
            response = self.client.chat.completions.create(
                model=settings.deepseek_model,
                messages=messages,  # type: ignore[arg-type]
                tools=tools,  # type: ignore[arg-type]
                tool_choice="auto",
                stream=False,
                temperature=0.1,
                extra_body={
                    "thinking": {
                        "type": "disabled",
                    },
                },
            )
        except OpenAIError as exc:
            raise AppException(
                message="AI 服务暂时不可用，请稍后重试",
                code="AGENT_MODEL_UNAVAILABLE",
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
            ) from exc

        message = response.choices[0].message
        tool_calls = [
            AgentModelToolCall(
                id=tool_call.id,
                name=tool_call.function.name,
                arguments=tool_call.function.arguments,
            )
            for tool_call in (message.tool_calls or [])
        ]

        return AgentModelReply(
            content=message.content,
            tool_calls=tool_calls,
        )


def get_agent_model_client() -> AgentModelClient:
    """FastAPI 依赖：创建当前配置的 Agent 模型客户端。"""

    return DeepSeekAgentClient()
