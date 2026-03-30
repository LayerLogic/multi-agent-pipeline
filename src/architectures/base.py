from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from src.client import BedrockClient
from src.metrics import AgentMessage


class BaseArchitecture(ABC):
    """Base class for all architecture implementations."""

    name: str

    def __init__(self, client: BedrockClient) -> None:
        self._client = client

    @abstractmethod
    def generate_tests(self, task: dict[str, Any]) -> tuple[str, list[AgentMessage]]:
        """Generate test code for a task.

        Returns:
            tuple of (generated_test_code, agent_message_trace)
        """

    def _format_task_prompt(self, task: dict[str, Any]) -> str:
        func_name = task["func_name"]
        return (
            f"Please write test methods for the function '{func_name}' "
            f"given the following program under test and function description.\n\n"
            f"Program under test:\n"
            f"----\n"
            f"{task['code_src']}\n"
            f"----\n\n"
            f"Function description for '{func_name}':\n"
            f"----\n"
            f"{task['description']}\n"
            f"----\n\n"
            f"Import the Solution class with: from under_test import Solution\n\n"
            f"Generate multiple test methods that cover different branches "
            f"and edge cases. Each test method should begin with:\n"
            f"def test_{func_name}...():\n"
            f"    solution = Solution()\n\n"
            f"Include all necessary imports. Output only Python code."
        )

    @staticmethod
    def extract_code(response: str) -> str:
        """Extract Python code from a response that may contain markdown fences."""
        pattern = r"```(?:python)?\s*\n(.*?)```"
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            return "\n".join(matches).strip()
        return response.strip()
