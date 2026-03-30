# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Research experiment comparing multi-agent LLM architectures for automated unit test generation. Evaluates three architecture patterns (single-agent, sequential/chain, hierarchical/supervisor) on the TestEval benchmark (210 LeetCode problems) using models via AWS Bedrock. Part of an MSc thesis at Chalmers on multi-agent LLM systems.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run experiment
python3 run_experiment.py
python3 run_experiment.py --models devstral2 sonnet4 --architectures single_agent sequential hierarchical --runs 5 --task-limit 100
python3 run_experiment.py --models devstral2 --architectures single_agent --runs 1 --task-limit 5 --resume

# Dashboard (visualize results)
python3 dashboard.py  # opens http://localhost:8050

# Run tests
python3 -m pytest
```

## Architecture

### Pipeline

```
run_experiment.py -> src/runner.py
  LLM generates tests, runs them locally via pytest, measures coverage
  Outputs: results/*.jsonl (RunRecords with metrics + coverage)
```

Each run iterates: **models x architectures x runs x tasks**. Results are resumable with `--resume`.

### Four Architecture Patterns (`src/architectures/`)

All extend `BaseArchitecture` and implement `generate_tests(task) -> (code, traces)`:

- **SingleAgentArchitecture** -- One LLM call, single pass. Baseline control.
- **SequentialArchitecture** -- Chain: Planner -> Coder -> Tester. Linear artifact-passing.
- **HierarchicalArchitecture** -- Supervisor delegates to Analyst/Writer workers using a structured protocol (`[DELEGATE:ANALYST]`, `[DELEGATE:WRITER]`, `[REVISION:...]`, `[FINAL]` markers). Max 6 supervisor turns.

### Benchmark (`src/testeval/`)

**TestEval** -- 210 LeetCode problems with cyclomatic complexity >= 10. Self-contained `class Solution` pattern. No Docker needed. Dataset at `benchmarks/TestEval/data/leetcode-py.jsonl`.

- `src/testeval/loader.py` -- Loads tasks from local JSONL
- `src/testeval/evaluator.py` -- Runs pytest + pytest-cov locally. Strips any re-defined Solution class from generated code to ensure coverage is measured against `under_test.py`.

### Key Modules

- **`src/client.py`** -- `BedrockClient` wraps `boto3` Bedrock Converse API. `CallAccumulator` tracks tokens/latency/cost across calls
- **`src/agent.py`** -- `Agent` holds conversation history and trace log. Each `run()` call appends user/assistant messages and records an `AgentMessage`
- **`src/metrics.py`** -- Data classes (`RunRecord`, `TaskMetrics`, `CoverageResult`, `AgentMessage`) and `ResultsWriter` (JSONL output, one file per architecture+model)
- **`src/prompts.py`** -- Loads prompt templates from `prompts/*.txt`
- **`src/config.py`** -- Model definitions (Devstral 2, Claude Sonnet 4 with pricing), `ExperimentConfig` defaults

### Prompt Templates (`prompts/`)

- `single_agent_full.txt` -- Single agent prompt
- `planner_full.txt` -- Sequential planner (produces plain text plan, no code)
- `coder_full.txt` -- Sequential coder (implements plan)
- `tester_full.txt` -- Sequential tester/reviewer
- `supervisor_full.txt` -- Hierarchical supervisor (defines delegation protocol)
- `analyst.txt` -- Hierarchical analysis worker
- `writer.txt` -- Hierarchical code writer

### Results

- `results/{architecture}_{model_id}.jsonl` -- RunRecords (one line per task per run)
- `results/historical/` -- Previous experiment runs

## Key Design Decisions

- **TestEval benchmark**: 210 self-contained LeetCode problems. No Docker required. Coverage measured locally via pytest-cov.
- **Solution class stripping**: The evaluator strips any re-defined `class Solution` from generated test code before measuring coverage, ensuring tests exercise `under_test.py` not a local copy.
- **Retry with feedback**: All architectures implement `retry_with_feedback()` receiving the full task prompt + failed code + error message. Max 3 retries.
- **Frozen dataclasses**: `LLMCallResult`, `AgentMessage`, `CoverageResult`, `TaskMetrics`, `ModelConfig`, `ExperimentConfig` are all `frozen=True`

## Environment

- Python 3.11+
- AWS credentials required for Bedrock access (region defaults to `eu-central-1`)
- `sortedcontainers` required (used by TestEval LeetCode solutions)
