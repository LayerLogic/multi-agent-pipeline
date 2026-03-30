from __future__ import annotations

import re
from typing import Any

from src.agent import Agent, AgentRole
from src.client import BedrockClient
from src.metrics import AgentMessage
from src.prompts import load_prompt

from .base import BaseArchitecture

_DELEGATE_PATTERN = re.compile(r"\[DELEGATE:(ANALYST|WRITER)\]\s*(.*?)(?=\[DELEGATE:|\[REVISION:|\[FINAL\]|$)", re.DOTALL)
_REVISION_PATTERN = re.compile(r"\[REVISION:(ANALYST|WRITER)\]\s*(.*?)(?=\[DELEGATE:|\[REVISION:|\[FINAL\]|$)", re.DOTALL)
_FINAL_PATTERN = re.compile(r"\[FINAL\]\s*(.*)", re.DOTALL)


class HierarchicalArchitecture(BaseArchitecture):
    """Hierarchical (centralized) architecture: Supervisor delegates to Workers.

    The Supervisor orchestrates an Analyst and a Writer agent.
    Information flows top-down (task delegation) and bottom-up (results).
    """

    name = "hierarchical"
    _max_supervisor_turns = 6

    def __init__(self, client: BedrockClient) -> None:
        super().__init__(client)
        self._roles = {
            "supervisor": AgentRole(name="supervisor", system_prompt=load_prompt("supervisor_full")),
            "analyst": AgentRole(name="analyst", system_prompt=load_prompt("analyst")),
            "writer": AgentRole(name="writer", system_prompt=load_prompt("writer")),
        }

    def generate_tests(self, task: dict[str, Any]) -> tuple[str, list[AgentMessage]]:
        roles = self._roles
        task_prompt = self._format_task_prompt(task)
        code_src = task["code_src"]
        all_traces: list[AgentMessage] = []

        supervisor = Agent(roles["supervisor"], self._client)
        analyst = Agent(roles["analyst"], self._client)
        writer = Agent(roles["writer"], self._client)

        # Initial supervisor call -- it will delegate to workers
        supervisor_response = supervisor.run(task_prompt, recipient="workers")
        all_traces.extend(supervisor.trace)

        final_code = ""

        for _turn in range(self._max_supervisor_turns):
            # Check if supervisor produced final output
            final_match = _FINAL_PATTERN.search(supervisor_response)
            if final_match:
                final_code = self.extract_code(final_match.group(1))
                break

            # Process delegations
            worker_results = self._process_delegations(
                supervisor_response, code_src, analyst, writer, all_traces,
            )

            # Process revisions
            revision_results = self._process_revisions(
                supervisor_response, analyst, writer, all_traces,
            )

            combined_feedback = worker_results + revision_results

            if not combined_feedback:
                # Supervisor didn't use protocol -- try to extract code directly
                final_code = self.extract_code(supervisor_response)
                break

            # Feed worker results back to supervisor
            feedback_prompt = "\n\n".join(combined_feedback)
            supervisor_response = supervisor.run(feedback_prompt, recipient="workers")
            all_traces.extend(supervisor.trace[-1:])
        else:
            # Max turns reached -- extract whatever we have
            final_code = self.extract_code(supervisor_response)

        return final_code, all_traces

    def _process_delegations(
        self,
        supervisor_response: str,
        code_src: str,
        analyst: Agent,
        writer: Agent,
        all_traces: list[AgentMessage],
    ) -> list[str]:
        results: list[str] = []
        for match in _DELEGATE_PATTERN.finditer(supervisor_response):
            worker_name = match.group(1)
            worker_task = match.group(2).strip()

            enriched_task = (
                f"Code under test:\n{code_src}\n\n"
                f"Task from supervisor:\n{worker_task}"
            )

            worker = analyst if worker_name == "ANALYST" else writer
            worker_response = worker.run(enriched_task, recipient="supervisor")
            all_traces.extend(worker.trace[-1:])

            results.append(
                f"Results from {worker_name}:\n----\n{worker_response}\n----"
            )
        return results

    def _process_revisions(
        self,
        supervisor_response: str,
        analyst: Agent,
        writer: Agent,
        all_traces: list[AgentMessage],
    ) -> list[str]:
        results: list[str] = []
        for match in _REVISION_PATTERN.finditer(supervisor_response):
            worker_name = match.group(1)
            revision_feedback = match.group(2).strip()

            worker = analyst if worker_name == "ANALYST" else writer
            worker_response = worker.run(
                f"Revision requested:\n{revision_feedback}",
                recipient="supervisor",
            )
            all_traces.extend(worker.trace[-1:])

            results.append(
                f"Revised results from {worker_name}:\n----\n{worker_response}\n----"
            )
        return results

    def retry_with_feedback(
        self, task: dict[str, Any], failed_code: str, error_message: str,
    ) -> tuple[str, list[AgentMessage]]:
        """Re-invoke the supervisor with execution error feedback for a retry."""
        roles = self._roles
        code_src = task["code_src"]

        supervisor = Agent(roles["supervisor"], self._client)
        writer = Agent(roles["writer"], self._client)
        all_traces: list[AgentMessage] = []

        task_prompt = self._format_task_prompt(task)
        prompt = (
            f"The previously generated tests failed execution.\n\n"
            f"{task_prompt}\n\n"
            f"Failed test code:\n"
            f"----\n"
            f"{failed_code}\n"
            f"----\n\n"
            f"Error:\n{error_message}\n\n"
            f"Delegate to WRITER to fix the tests. Then output the corrected "
            f"tests after [FINAL]."
        )

        supervisor_response = supervisor.run(prompt, recipient="workers")
        all_traces.extend(supervisor.trace)

        final_match = _FINAL_PATTERN.search(supervisor_response)
        if final_match:
            return self.extract_code(final_match.group(1)), all_traces

        # Process any delegations to writer
        for match in _DELEGATE_PATTERN.finditer(supervisor_response):
            if match.group(1) == "WRITER":
                enriched = (
                    f"Code under test:\n{code_src}\n\n"
                    f"Task:\n{match.group(2).strip()}"
                )
                writer_response = writer.run(enriched, recipient="supervisor")
                all_traces.extend(writer.trace[-1:])

                final_response = supervisor.run(
                    f"Results from WRITER:\n----\n{writer_response}\n----\n\n"
                    f"Please output the final corrected tests after [FINAL].",
                    recipient="output",
                )
                all_traces.extend(supervisor.trace[-1:])

                final_match = _FINAL_PATTERN.search(final_response)
                if final_match:
                    return self.extract_code(final_match.group(1)), all_traces
                return self.extract_code(final_response), all_traces

        return self.extract_code(supervisor_response), all_traces
