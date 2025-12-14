"""Claude API node executor for FlowPilot."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

import anthropic

from flowpilot.config import ConfigError, get_anthropic_api_key
from flowpilot.engine.context import NodeResult
from flowpilot.engine.executor import ExecutorRegistry, NodeExecutor

if TYPE_CHECKING:
    from flowpilot.engine.context import ExecutionContext
    from flowpilot.models import ClaudeApiNode

# Model pricing (per 1M tokens) - as of 2024/2025
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
}

# Default pricing for unknown models
DEFAULT_PRICING = {"input": 3.00, "output": 15.00}


@ExecutorRegistry.register("claude-api")
class ClaudeApiExecutor(NodeExecutor):
    """Execute prompts via Anthropic API directly."""

    def __init__(self) -> None:
        """Initialize the executor."""
        self._client: anthropic.AsyncAnthropic | None = None

    def _get_client(self) -> anthropic.AsyncAnthropic:
        """Get or create Anthropic async client.

        Returns:
            AsyncAnthropic client instance.

        Raises:
            ConfigError: If API key is not configured.
        """
        if self._client is None:
            api_key = get_anthropic_api_key()
            self._client = anthropic.AsyncAnthropic(api_key=api_key)
        return self._client

    async def execute(
        self,
        node: ClaudeApiNode,  # type: ignore[override]
        context: ExecutionContext,
    ) -> NodeResult:
        """Execute a prompt via Anthropic API.

        Args:
            node: The claude-api node to execute.
            context: The execution context.

        Returns:
            NodeResult with API response.
        """
        started_at = datetime.now()

        try:
            client = self._get_client()
        except ConfigError as e:
            return NodeResult(
                status="error",
                error_message=str(e),
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

        # Build messages
        messages = node.messages or [{"role": "user", "content": node.prompt}]

        # Build request kwargs
        kwargs: dict[str, Any] = {
            "model": node.model,
            "max_tokens": node.max_tokens,
            "messages": messages,
        }

        # System prompt handling
        system_prompt = node.system

        # JSON mode - add instruction to system prompt
        if node.output_format == "json":
            json_instruction = "\n\nRespond with valid JSON only."
            if node.json_schema:
                json_instruction += f" Use this schema: {json.dumps(node.json_schema)}"

            if system_prompt:
                system_prompt += json_instruction
            else:
                system_prompt = json_instruction.strip()

        if system_prompt:
            kwargs["system"] = system_prompt

        # Optional generation parameters
        if node.temperature is not None:
            kwargs["temperature"] = node.temperature

        if node.top_p is not None:
            kwargs["top_p"] = node.top_p

        if node.top_k is not None:
            kwargs["top_k"] = node.top_k

        if node.stop_sequences:
            kwargs["stop_sequences"] = node.stop_sequences

        if node.metadata:
            kwargs["metadata"] = {"user_id": node.metadata.get("user_id", "")}

        try:
            # Make API call with timeout
            response = await asyncio.wait_for(
                client.messages.create(**kwargs),
                timeout=node.timeout,
            )

            # Extract response text
            output_text = ""
            for block in response.content:
                if block.type == "text":
                    output_text += block.text

            # Parse JSON if requested
            parsed_data: dict[str, Any] | None = None
            if node.output_format == "json":
                try:
                    parsed_data = json.loads(output_text)
                except json.JSONDecodeError as e:
                    parsed_data = {"parse_error": str(e), "raw": output_text}

            # Calculate cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = self._calculate_cost(node.model, input_tokens, output_tokens)

            return NodeResult(
                status="success",
                output=output_text,
                data={
                    "model": node.model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                    "cost_usd": cost,
                    "stop_reason": response.stop_reason,
                    "parsed": parsed_data,
                },
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

        except anthropic.APIConnectionError as e:
            return NodeResult(
                status="error",
                error_message=f"API connection error: {e}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except anthropic.RateLimitError as e:
            return NodeResult(
                status="error",
                error_message=f"Rate limit exceeded: {e}. Retry after delay.",
                data={"retry_after": getattr(e, "retry_after", 60)},
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except anthropic.APIStatusError as e:
            return NodeResult(
                status="error",
                error_message=f"API error ({e.status_code}): {e}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except TimeoutError:
            return NodeResult(
                status="error",
                error_message=f"API request timed out after {node.timeout}s",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )
        except Exception as e:
            return NodeResult(
                status="error",
                error_message=f"Unexpected error: {e}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(),
            )

    def _calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate API cost in USD.

        Args:
            model: The model ID.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.

        Returns:
            Estimated cost in USD.
        """
        # Find pricing for model (exact match or prefix match)
        pricing = MODEL_PRICING.get(model)

        if not pricing:
            # Try prefix matching for versioned models
            for model_name, price in MODEL_PRICING.items():
                if model.startswith(model_name.rsplit("-", 1)[0]):
                    pricing = price
                    break

        if not pricing:
            pricing = DEFAULT_PRICING

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return round(input_cost + output_cost, 6)

    @staticmethod
    def _duration_ms(started_at: datetime) -> int:
        """Calculate duration in milliseconds."""
        return int((datetime.now() - started_at).total_seconds() * 1000)
