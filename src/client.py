from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import boto3
from botocore.config import Config as BotoConfig

from src.config import ExperimentConfig, ModelConfig


@dataclass(frozen=True)
class LLMCallResult:
    content: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    model_id: str
    stop_reason: str


@dataclass
class CallAccumulator:
    """Accumulates token counts and latency across multiple LLM calls."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_latency_s: float = 0.0
    call_count: int = 0
    calls: list[LLMCallResult] = field(default_factory=list)

    def record(self, result: LLMCallResult) -> None:
        self.total_input_tokens += result.input_tokens
        self.total_output_tokens += result.output_tokens
        self.total_latency_s += result.latency_s
        self.call_count += 1
        self.calls.append(result)

    def estimated_cost(self, model: ModelConfig) -> float:
        input_cost = (self.total_input_tokens / 1_000_000) * model.input_price_per_1m
        output_cost = (self.total_output_tokens / 1_000_000) * model.output_price_per_1m
        return input_cost + output_cost

    def reset(self) -> None:
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_latency_s = 0.0
        self.call_count = 0
        self.calls = []


class BedrockClient:
    """Thin wrapper around Bedrock Converse API with automatic metrics tracking."""

    def __init__(self, model: ModelConfig, config: ExperimentConfig) -> None:
        self._model = model
        self._config = config
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=config.aws_region,
            config=BotoConfig(
                read_timeout=300,
                connect_timeout=10,
                retries={"max_attempts": 3},
            ),
        )
        self.accumulator = CallAccumulator()

    @property
    def model(self) -> ModelConfig:
        return self._model

    def invoke(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMCallResult:
        inference_config: dict[str, Any] = {
            "temperature": temperature if temperature is not None else self._config.temperature,
            "maxTokens": max_tokens or self._config.max_tokens,
            "topP": self._config.top_p,
        }

        kwargs: dict[str, Any] = {
            "modelId": self._model.model_id,
            "messages": messages,
            "inferenceConfig": inference_config,
        }

        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]

        start = time.perf_counter()
        response = self._client.converse(**kwargs)
        latency = time.perf_counter() - start

        usage = response.get("usage", {})
        output_content = response.get("output", {}).get("message", {}).get("content", [])
        text = output_content[0].get("text", "") if output_content else ""

        result = LLMCallResult(
            content=text,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            latency_s=latency,
            model_id=self._model.model_id,
            stop_reason=response.get("stopReason", "unknown"),
        )

        self.accumulator.record(result)
        return result

    def reset_accumulator(self) -> None:
        self.accumulator.reset()
