from __future__ import annotations

from typing import Any

from src.agent import Agent, AgentRole
from src.client import BedrockClient
from src.metrics import AgentMessage
from src.prompts import load_prompt

from .base import BaseArchitecture


class SingleAgentArchitecture(BaseArchitecture):
    """Single-agent baseline: one LLM generates tests in a single pass."""

    name = "single_agent"

    def __init__(self, client: BedrockClient) -> None:
        super().__init__(client)
        self._role = AgentRole(
            name="single_agent",
            system_prompt=load_prompt("single_agent_full"),
        )

    def generate_tests(self, task: dict[str, Any]) -> tuple[str, list[AgentMessage]]:
        agent = Agent(self._role, self._client)
        prompt = self._format_task_prompt(task)

        response = agent.run(prompt, recipient="output")
        test_code = self.extract_code(response)

        return test_code, agent.trace

    def retry_with_feedback(
        self, task: dict[str, Any], failed_code: str, error_message: str,
    ) -> tuple[str, list[AgentMessage]]:
        """Re-invoke the single agent with execution error feedback."""
        agent = Agent(self._role, self._client)
        prompt = (
            f"{self._format_task_prompt(task)}\n\n"
            f"A previous attempt produced the following test code:\n"
            f"----\n"
            f"{failed_code}\n"
            f"----\n\n"
            f"Execution results: FAILED\n"
            f"Error:\n{error_message}\n\n"
            f"Fix the test code and return a corrected version."
        )
        response = agent.run(prompt, recipient="output")
        fixed_code = self.extract_code(response)
        return fixed_code, agent.trace
