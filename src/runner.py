"""Experiment runner: generates tests, evaluates locally, writes results.

Iterates models x architectures x runs x tasks. For each task:
1. Generate test code via the architecture's LLM agents
2. Run tests locally (retry with feedback on failure)
3. Evaluate coverage on passing tests
4. Write RunRecord with metrics + coverage
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from tqdm import tqdm

from src.architectures.base import BaseArchitecture
from src.architectures.hierarchical import HierarchicalArchitecture
from src.architectures.sequential import SequentialArchitecture
from src.architectures.single_agent import SingleAgentArchitecture
from src.client import BedrockClient
from src.config import ARCHITECTURES, ALL_MODELS, EXPERIMENT, ExperimentConfig, ModelConfig
from src.metrics import AgentMessage, CoverageResult, ResultsWriter, RunRecord, TaskMetrics
from src.testeval.evaluator import quick_execute, evaluate_tests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _build_architecture(name: str, client: BedrockClient) -> BaseArchitecture:
    mapping = {
        "single_agent": SingleAgentArchitecture,
        "sequential": SequentialArchitecture,
        "hierarchical": HierarchicalArchitecture,
    }
    return mapping[name](client)


def _load_tasks() -> list[dict[str, Any]]:
    from src.testeval.loader import load_testeval
    return load_testeval()


def _get_task_id(task: dict[str, Any]) -> str:
    return task["task_id"]


def _get_task_title(task: dict[str, Any]) -> str:
    return f"{task.get('repo', '')} -- {task.get('code_file', '')}"


def _build_run_id(arch: str, model_id: str, run_num: int, task_id: str) -> str:
    safe_model = model_id.split(".")[-1]
    safe_task = task_id.replace("/", "_").replace(" ", "_")
    return f"{arch}_{safe_model}_run{run_num}_{safe_task}"


def run_single_task(
    architecture: BaseArchitecture,
    task: dict[str, Any],
    client: BedrockClient,
    config: ExperimentConfig,
    run_number: int,
) -> RunRecord:
    """Generate tests for one task, evaluate locally with retries."""
    task_id = _get_task_id(task)
    run_id = _build_run_id(architecture.name, client.model.model_id, run_number, task_id)

    record = RunRecord(
        run_id=run_id,
        architecture=architecture.name,
        model_id=client.model.model_id,
        model_display_name=client.model.display_name,
        task_id=task_id,
        instance_id=task["instance_id"],
        task_num=task.get("task_num", task.get("index", 0)),
        task_title=_get_task_title(task),
        difficulty=task.get("difficulty", 0),
        run_number=run_number,
        temperature=config.temperature,
    )

    client.reset_accumulator()
    task_start = time.perf_counter()
    all_traces: list[AgentMessage] = []

    try:
        test_code, traces = architecture.generate_tests(task)
        all_traces.extend(traces)

        # Retry loop
        for retry in range(config.max_retries):
            passed, error_msg = quick_execute(task, test_code, config.test_execution_timeout_s)

            if passed:
                record.retry_count = retry
                break

            logger.info(
                "  Retry %d/%d for %s: %s",
                retry + 1, config.max_retries, task_id, error_msg[:100],
            )

            if hasattr(architecture, "retry_with_feedback"):
                test_code, retry_traces = architecture.retry_with_feedback(task, test_code, error_msg)
                all_traces.extend(retry_traces)
            else:
                test_code, retry_traces = architecture.generate_tests(task)
                all_traces.extend(retry_traces)

            record.retry_count = retry + 1
        else:
            passed, _ = quick_execute(task, test_code, config.test_execution_timeout_s)

        coverage = evaluate_tests(task, test_code, config.test_execution_timeout_s)

    except Exception as e:
        logger.error("  Exception on %s: %s", task_id, str(e))
        test_code = ""
        coverage = CoverageResult(passed=False, error_message=str(e))
        all_traces = []

    task_latency = time.perf_counter() - task_start
    acc = client.accumulator

    record.generated_tests = test_code
    record.agent_trace = all_traces
    record.coverage = coverage
    record.metrics = TaskMetrics(
        total_input_tokens=acc.total_input_tokens,
        total_output_tokens=acc.total_output_tokens,
        estimated_cost_usd=acc.estimated_cost(client.model),
        end_to_end_latency_s=round(task_latency, 3),
        agent_turns=len(all_traces),
        llm_calls=acc.call_count,
    )

    return record


def _load_completed_task_ids(
    results_dir: str, architecture: str, model_id: str, run_num: int,
) -> set[str]:
    """Load task_ids that already have a record for a given run."""
    safe_model = model_id.replace(".", "_").replace(":", "_")
    path = Path(results_dir) / f"{architecture}_{safe_model}.jsonl"
    if not path.exists():
        return set()

    completed: set[str] = set()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("run_number") == run_num:
                tid = r.get("task_id", "")
                if tid:
                    completed.add(tid)
    return completed


def _load_errored_task_ids(results_dir: str, architecture: str, model_id: str) -> set[str]:
    """Find task_ids whose last record was an error (empty generated_tests)."""
    safe_model = model_id.replace(".", "_").replace(":", "_")
    path = Path(results_dir) / f"{architecture}_{safe_model}.jsonl"
    if not path.exists():
        return set()

    last_record: dict[str, dict] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            tid = r.get("task_id", "")
            if tid:
                last_record[tid] = r

    errored = set()
    for tid, r in last_record.items():
        if r.get("generated_tests", "") == "":
            errored.add(tid)
    return errored


def run_experiment(
    models: tuple[ModelConfig, ...] | None = None,
    architectures: tuple[str, ...] | None = None,
    config: ExperimentConfig | None = None,
    task_limit: int | None = None,
    retry_errors: bool = False,
    resume: bool = False,
) -> None:
    """Run the full experiment: models x architectures x runs x tasks."""
    config = config or EXPERIMENT
    models = models or ALL_MODELS
    architectures = architectures or ARCHITECTURES

    tasks = _load_tasks()
    if task_limit:
        tasks = tasks[:task_limit]

    results_writer = ResultsWriter(config.results_dir)

    for model in models:
        logger.info("=== Model: %s ===", model.display_name)
        client = BedrockClient(model, config)

        for arch_name in architectures:
            logger.info("--- Architecture: %s ---", arch_name)
            architecture = _build_architecture(arch_name, client)

            if retry_errors:
                errored_ids = _load_errored_task_ids(config.results_dir, arch_name, model.model_id)
                run_tasks = [t for t in tasks if t["task_id"] in errored_ids]
                if not run_tasks:
                    logger.info("  No errored tasks to retry, skipping")
                    continue
                logger.info("  Retrying %d errored tasks", len(run_tasks))
            else:
                run_tasks = tasks

            total = len(run_tasks)
            logger.info(
                "  %d tasks x %d runs",
                total, config.runs_per_architecture,
            )

            for run_num in range(1, config.runs_per_architecture + 1):
                logger.info("  Run %d/%d", run_num, config.runs_per_architecture)

                if resume:
                    completed_ids = _load_completed_task_ids(
                        config.results_dir, arch_name, model.model_id, run_num,
                    )
                    if completed_ids:
                        logger.info(
                            "  Resuming: skipping %d already-completed tasks",
                            len(completed_ids),
                        )
                else:
                    completed_ids = set()

                for task in tqdm(run_tasks, desc=f"{arch_name} run {run_num}", unit="task"):
                    if completed_ids and _get_task_id(task) in completed_ids:
                        continue

                    record = run_single_task(
                        architecture, task, client, config, run_num,
                    )
                    results_writer.write(record)

                    status = "PASS" if record.coverage and record.coverage.passed else "FAIL"
                    logger.debug(
                        "  %s | %s | tokens=%d | latency=%.1fs",
                        _get_task_id(task), status,
                        record.metrics.total_input_tokens + record.metrics.total_output_tokens if record.metrics else 0,
                        record.metrics.end_to_end_latency_s if record.metrics else 0,
                    )

    logger.info("Experiment complete. Results written to %s/", config.results_dir)
