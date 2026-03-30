"""Load TestEval benchmark tasks from the local JSONL dataset.

TestEval contains 210 LeetCode problems with cyclomatic complexity >= 10.
Each task is a self-contained Solution class -- no Docker or repo context needed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATASET_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "TestEval" / "data" / "leetcode-py.jsonl"

DIFFICULTY_MAP = {1: "Easy", 2: "Medium", 3: "Hard"}


def load_testeval(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load TestEval dataset from JSONL file.

    Returns a list of task dicts with a normalised interface that
    the runner and architectures can consume alongside TestGenEval tasks.
    """
    data_path = Path(path) if path else DATASET_PATH
    if not data_path.exists():
        raise FileNotFoundError(
            f"TestEval dataset not found at {data_path}. "
            "Download it from https://github.com/LLM4SoftwareTesting/TestEval"
        )

    tasks: list[dict[str, Any]] = []
    with open(data_path) as f:
        for idx, line in enumerate(f):
            row = json.loads(line.strip())
            tasks.append({
                # Normalised keys used by the runner
                "task_id": f"testeval-{row['task_num']}",
                "instance_id": f"testeval-{row['task_num']}",
                "task_num": row["task_num"],
                "task_title": row["task_title"],
                "difficulty": row["difficulty"],
                "func_name": row["func_name"],
                "description": row["description"],
                "code_src": row["python_solution"],
                "blocks": row.get("blocks", []),
                "target_lines": row.get("target_lines", []),
                # Compatibility fields expected by runner
                "code_file": f"leetcode/{row['task_num']}_{row['func_name']}.py",
                "repo": "LeetCode",
                "local_imports": "",
                "index": idx,
                # Marker so evaluator/architecture can branch
                "benchmark": "testeval",
            })

    return tasks


def format_task_summary(task: dict[str, Any]) -> str:
    """Return a short human-readable summary of a TestEval task."""
    diff = DIFFICULTY_MAP.get(task["difficulty"], "?")
    return f"[{task['task_num']}] {task['task_title']} ({diff})"
