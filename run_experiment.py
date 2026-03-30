"""Phase 1: Generate tests via multi-agent architectures.

Produces RunRecords (token/latency/coverage metrics) as JSONL files.

Usage:
  python run_experiment.py
  python run_experiment.py --models devstral2 sonnet4 --architectures single_agent sequential hierarchical debate --runs 5 --task-limit 100
"""
from __future__ import annotations

import argparse

from src.config import ALL_MODELS, ARCHITECTURES, EXPERIMENT, DEVSTRAL_2, CLAUDE_SONNET_4, ExperimentConfig
from src.runner import run_experiment


MODEL_MAP = {
    "devstral2": DEVSTRAL_2,
    "sonnet4": CLAUDE_SONNET_4,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate tests via multi-agent architectures (TestEval benchmark)",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(MODEL_MAP.keys()),
        default=list(MODEL_MAP.keys()),
        help="Models to evaluate (default: all)",
    )
    parser.add_argument(
        "--architectures",
        nargs="+",
        choices=list(ARCHITECTURES),
        default=list(ARCHITECTURES),
        help="Architectures to evaluate (default: all)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=EXPERIMENT.runs_per_architecture,
        help=f"Runs per architecture (default: {EXPERIMENT.runs_per_architecture})",
    )
    parser.add_argument(
        "--task-limit",
        type=int,
        default=None,
        help="Limit number of tasks (for testing). Default: all 210 tasks",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=EXPERIMENT.temperature,
        help=f"LLM temperature (default: {EXPERIMENT.temperature})",
    )
    parser.add_argument(
        "--region",
        type=str,
        default=EXPERIMENT.aws_region,
        help=f"AWS region (default: {EXPERIMENT.aws_region})",
    )
    parser.add_argument(
        "--retry-errors",
        action="store_true",
        help="Only rerun tasks that errored (e.g. timeout, expired token)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip tasks that already have results (resume interrupted runs)",
    )

    args = parser.parse_args()

    models = tuple(MODEL_MAP[m] for m in args.models)
    architectures = tuple(args.architectures)
    total_tasks = args.task_limit or 210

    config = ExperimentConfig(
        runs_per_architecture=args.runs,
        temperature=args.temperature,
        aws_region=args.region,
    )

    print(f"Experiment: Test Generation (TestEval Benchmark)")
    print(f"Models:         {[m.display_name for m in models]}")
    print(f"Architectures:  {list(architectures)}")
    print(f"Runs:           {config.runs_per_architecture}")
    print(f"Tasks:          {total_tasks}")
    print(f"Temperature:    {config.temperature}")
    print(f"Max retries:    {config.max_retries}")
    print(f"Region:         {config.aws_region}")
    print()

    run_experiment(
        models=models,
        architectures=architectures,
        config=config,
        task_limit=args.task_limit,
        retry_errors=args.retry_errors,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
