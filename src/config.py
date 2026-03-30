from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class ModelConfig:
    model_id: str
    display_name: str
    input_price_per_1m: float
    output_price_per_1m: float


DEVSTRAL_2: Final = ModelConfig(
    model_id="mistral.devstral-2-123b",
    display_name="Devstral 2 123B",
    input_price_per_1m=1.00,
    output_price_per_1m=3.00,
)

CLAUDE_SONNET_4: Final = ModelConfig(
    model_id="eu.anthropic.claude-sonnet-4-20250514-v1:0",
    display_name="Claude Sonnet 4",
    input_price_per_1m=3.00,
    output_price_per_1m=15.00,
)

ALL_MODELS: Final = (DEVSTRAL_2, CLAUDE_SONNET_4)


@dataclass(frozen=True)
class ExperimentConfig:
    runs_per_architecture: int = 1
    temperature: float = 0.2
    max_retries: int = 3
    max_tokens: int = 4096
    top_p: float = 1.0
    test_execution_timeout_s: int = 30
    aws_region: str = "eu-central-1"
    results_dir: str = "results"


EXPERIMENT: Final = ExperimentConfig()

ARCHITECTURES: Final = ("single_agent", "sequential", "hierarchical")
