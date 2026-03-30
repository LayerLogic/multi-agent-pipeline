from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from src.client import BedrockClient, LLMCallResult
from src.metrics import AgentMessage


@dataclass(frozen=True)
class AgentRole:
    """Defines an agent's identity and system prompt."""

    name: str
    system_prompt: str


class Agent:
    """A single LLM-powered agent with a role, message history, and trace logging."""

    def __init__(self, role: AgentRole, client: BedrockClient) -> None:
        self._role = role
        self._client = client
        self._history: list[dict[str, Any]] = []
        self._trace: list[AgentMessage] = []

    @property
    def name(self) -> str:
        return self._role.name

    @property
    def trace(self) -> list[AgentMessage]:
        return list(self._trace)

    def run(self, user_message: str, recipient: str = "system") -> str:
        self._history.append({
            "role": "user",
            "content": [{"text": user_message}],
        })

        result = self._client.invoke(
            messages=list(self._history),
            system_prompt=self._role.system_prompt,
        )

        self._history.append({
            "role": "assistant",
            "content": [{"text": result.content}],
        })

        self._trace.append(AgentMessage(
            from_agent=self._role.name,
            to_agent=recipient,
            content=result.content,
            timestamp=time.time(),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        ))

        return result.content

    def reset(self) -> None:
        self._history = []
        self._trace = []
