from __future__ import annotations

from typing import Any

from src.agent import Agent, AgentRole
from src.client import BedrockClient
from src.metrics import AgentMessage
from src.prompts import load_prompt

from .base import BaseArchitecture


class SequentialArchitecture(BaseArchitecture):
    """Sequential (chain) architecture: Planner -> Coder -> Tester.

    Each agent passes its artifact to the next in a linear pipeline.
    The Tester agent only activates if the generated tests fail execution.
    """

    name = "sequential"

    def __init__(self, client: BedrockClient) -> None:
        super().__init__(client)
        self._roles = {
            "planner": AgentRole(name="planner", system_prompt=load_prompt("planner_full")),
            "coder": AgentRole(name="coder", system_prompt=load_prompt("coder_full")),
            "tester": AgentRole(name="tester", system_prompt=load_prompt("tester_full")),
        }

    def generate_tests(self, task: dict[str, Any]) -> tuple[str, list[AgentMessage]]:
        roles = self._roles
        task_prompt = self._format_task_prompt(task)
        code_src = task["code_src"]
        all_traces: list[AgentMessage] = []

        # Stage 1: Planner analyzes the function and creates a test plan
        planner = Agent(roles["planner"], self._client)
        test_plan = planner.run(task_prompt, recipient="coder")
        all_traces.extend(planner.trace)

        # Stage 2: Coder translates the plan into executable test code
        coder = Agent(roles["coder"], self._client)
        coder_prompt = (
            f"{task_prompt}\n\n"
            f"Test plan from the planning phase:\n"
            f"----\n"
            f"{test_plan}\n"
            f"----"
        )
        code_response = coder.run(coder_prompt, recipient="tester")
        test_code = self.extract_code(code_response)
        all_traces.extend(coder.trace)

        # Stage 3: Tester reviews for obvious issues
        tester = Agent(roles["tester"], self._client)
        review_prompt = (
            f"Program under test:\n"
            f"----\n"
            f"{code_src}\n"
            f"----\n\n"
            f"Generated test code:\n"
            f"----\n"
            f"{test_code}\n"
            f"----\n\n"
            f"Execution results: Not yet executed. Please review the code "
            f"for obvious issues and return the corrected version."
        )
        reviewed_response = tester.run(review_prompt, recipient="output")
        reviewed_code = self.extract_code(reviewed_response)
        all_traces.extend(tester.trace)

        return reviewed_code, all_traces

    def retry_with_feedback(
        self, task: dict[str, Any], failed_code: str, error_message: str,
    ) -> tuple[str, list[AgentMessage]]:
        """Re-invoke the tester agent with execution error feedback."""
        roles = self._roles
        task_prompt = self._format_task_prompt(task)

        tester = Agent(roles["tester"], self._client)
        prompt = (
            f"{task_prompt}\n\n"
            f"Generated test code:\n"
            f"----\n"
            f"{failed_code}\n"
            f"----\n\n"
            f"Execution results: FAILED\n"
            f"Error:\n{error_message}"
        )
        response = tester.run(prompt, recipient="output")
        fixed_code = self.extract_code(response)
        return fixed_code, tester.trace
