from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentMessage:
    """A single inter-agent communication record."""

    from_agent: str
    to_agent: str
    content: str
    timestamp: float
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class CoverageResult:
    """Test execution and coverage outcome for a single task."""

    passed: bool
    error_message: str | None = None
    line_coverage: float = 0.0
    branch_coverage: float = 0.0
    mutation_score: float = 0.0
    tests_generated: int = 0
    tests_passed: int = 0


@dataclass(frozen=True)
class TaskMetrics:
    """All metrics collected for a single task execution."""

    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float
    end_to_end_latency_s: float
    agent_turns: int
    llm_calls: int


@dataclass
class RunRecord:
    """Complete record for one task in one run."""

    run_id: str
    architecture: str
    model_id: str
    model_display_name: str
    task_id: str
    instance_id: str
    task_num: int
    task_title: str
    difficulty: int
    run_number: int
    temperature: float
    metrics: TaskMetrics | None = None
    coverage: CoverageResult | None = None
    agent_trace: list[AgentMessage] = field(default_factory=list)
    generated_tests: str = ""
    retry_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        data = {
            "run_id": self.run_id,
            "architecture": self.architecture,
            "model_id": self.model_id,
            "model_display_name": self.model_display_name,
            "task_id": self.task_id,
            "instance_id": self.instance_id,
            "task_num": self.task_num,
            "task_title": self.task_title,
            "difficulty": self.difficulty,
            "run_number": self.run_number,
            "temperature": self.temperature,
            "generated_tests": self.generated_tests,
            "retry_count": self.retry_count,
        }
        if self.metrics:
            data["metrics"] = asdict(self.metrics)
        if self.coverage:
            data["coverage"] = asdict(self.coverage)
        data["agent_trace"] = [asdict(msg) for msg in self.agent_trace]
        return data


class ResultsWriter:
    """Appends RunRecords to a JSONL file, one per architecture+model combo."""

    def __init__(self, results_dir: str) -> None:
        self._results_dir = Path(results_dir)
        self._results_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, architecture: str, model_id: str) -> Path:
        safe_model = model_id.replace(".", "_").replace(":", "_")
        return self._results_dir / f"{architecture}_{safe_model}.jsonl"

    def write(self, record: RunRecord) -> None:
        path = self._file_path(record.architecture, record.model_id)
        with open(path, "a") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

    def load_all(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in sorted(self._results_dir.glob("*.jsonl")):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        return records
