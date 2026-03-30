# Multi-Agent Pipeline for Automated Test Generation

A research experiment comparing multi-agent LLM architectures for automated unit test generation. Evaluates three architecture patterns on the [TestEval](https://github.com/LLM4SoftwareTesting/TestEval) benchmark (210 LeetCode problems) using models via AWS Bedrock.

Part of an MSc thesis at Chalmers University of Technology: *Architectural Patterns and Trade-offs in Multi-Agent LLM-based Systems*.

## Architecture Patterns

| Pattern | Agents | Flow | LLM Calls |
|---------|--------|------|-----------|
| **Single Agent** | 1 (baseline) | Single pass | 1 |
| **Sequential** | 3 (Planner, Coder, Tester) | Linear chain | 3 |
| **Hierarchical** | 3 (Supervisor, Analyst, Writer) | Top-down delegation | 6-12 |

All architectures support retry with feedback (up to 3 retries). On failure, the error message is fed back to the relevant agent for self-correction.

## Prerequisites

- Python 3.11+
- AWS account with Bedrock access enabled for:
  - `mistral.devstral-2-123b` (Devstral 2)
  - `eu.anthropic.claude-sonnet-4-20250514-v1:0` (Claude Sonnet 4)
- AWS credentials configured (`aws configure` or environment variables)

## Setup

```bash
git clone <repo-url>
cd multi-agents-pipeline

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the Experiment

### Quick test (5 tasks, 1 model, 1 architecture)

```bash
python3 run_experiment.py --models devstral2 --architectures single_agent --runs 1 --task-limit 5
```

### Full experiment

```bash
python3 run_experiment.py --models devstral2 sonnet4 --architectures single_agent sequential hierarchical --runs 5 --task-limit 100
```

### CLI options

| Flag | Description | Default |
|------|-------------|---------|
| `--models` | Models to use: `devstral2`, `sonnet4` | All |
| `--architectures` | Patterns: `single_agent`, `sequential`, `hierarchical` | All |
| `--runs` | Runs per architecture (for variance) | 1 |
| `--task-limit` | Number of tasks to run (out of 210) | All 210 |
| `--temperature` | LLM sampling temperature | 0.2 |
| `--region` | AWS Bedrock region | eu-central-1 |
| `--resume` | Skip already-completed tasks | Off |
| `--retry-errors` | Only re-run tasks that errored | Off |

### Resuming interrupted runs

If a run is interrupted, re-run with `--resume` to skip completed tasks:

```bash
python3 run_experiment.py --models devstral2 --runs 5 --task-limit 100 --resume
```

## Viewing Results

```bash
python3 dashboard.py
```

Opens a web dashboard at `http://localhost:8050` with:
- KPI summary (pass rate, coverage, cost, latency)
- Charts comparing architectures
- Filterable by model, architecture, and run number
- Clickable task detail view with agent interaction traces

Results are stored as JSONL in `results/`. Each line is a `RunRecord` containing metrics, coverage, generated test code, and the full agent communication trace.

## Project Structure

```
.
├── run_experiment.py              # CLI entry point
├── dashboard.py                   # Results visualization
├── requirements.txt
├── benchmarks/TestEval/
│   └── data/leetcode-py.jsonl     # 210 LeetCode tasks
├── prompts/                       # System prompts for each agent role
│   ├── single_agent_full.txt
│   ├── planner_full.txt
│   ├── coder_full.txt
│   ├── tester_full.txt
│   ├── supervisor_full.txt
│   ├── analyst.txt
│   └── writer.txt
├── src/
│   ├── runner.py                  # Experiment orchestration
│   ├── agent.py                   # LLM agent with conversation history
│   ├── client.py                  # AWS Bedrock API wrapper
│   ├── config.py                  # Model and experiment configuration
│   ├── metrics.py                 # Data classes and results writer
│   ├── prompts.py                 # Prompt template loader
│   ├── architectures/
│   │   ├── base.py                # Abstract base class
│   │   ├── single_agent.py
│   │   ├── sequential.py
│   │   └── hierarchical.py
│   └── testeval/
│       ├── loader.py              # Loads TestEval dataset
│       └── evaluator.py           # Runs pytest + coverage measurement
└── results/                       # Output JSONL files
```

## Metrics Collected

For each task, the pipeline records:

- **Pass rate** -- Did all generated tests pass?
- **Line coverage** -- % of source lines exercised by tests
- **Branch coverage** -- % of branches exercised by tests
- **Token usage** -- Input and output tokens across all LLM calls
- **Cost** -- Estimated USD based on model pricing
- **Latency** -- End-to-end wall clock time
- **Agent turns** -- Number of inter-agent messages
- **Retry count** -- How many retries were needed
- **Agent trace** -- Full message log between agents

## Benchmark

[TestEval](https://github.com/LLM4SoftwareTesting/TestEval) contains 210 LeetCode problems filtered by cyclomatic complexity >= 10. Each task is a self-contained Python `Solution` class with a function description. No Docker or external dependencies needed -- tests run locally via pytest.

Distribution: 9 easy, 100 medium, 101 hard problems.
