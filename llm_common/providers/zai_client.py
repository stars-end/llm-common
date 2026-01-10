"""z.ai LLM client implementation."""

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx
from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from llm_common.core import (
    APIKeyError,
    LLMClient,
    LLMConfig,
    LLMError,
    LLMMessage,
    LLMResponse,
    LLMUsage,
    MessageRole,
    RateLimitError,
    TimeoutError,
)


@dataclass
class StreamChunk:
    """A chunk from streaming completion with GLM-4.7 support.

    Supports content, reasoning (thinking), and tool calls.
    """

    content: str = ""
    reasoning_content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None


class ZaiClient(LLMClient):
    """z.ai LLM client with OpenAI compatibility."""

    BASE_URL = "https://api.z.ai/api/coding/paas/v4"

    # Pricing per 1M tokens (as of 2025-01)
    PRICING = {
        # NOTE: Keep keys unique; Python dict literals overwrite duplicates.
        # For now, treat glm-4.7 as free-tier in cost estimation.
        "glm-4.7": {"input": 0.0, "output": 0.0},
    }

    def __init__(self, config: LLMConfig) -> None:
        """Initialize z.ai client.

        Args:
            config: LLM configuration

        Raises:
            APIKeyError: If API key is missing
        """
        super().__init__(config)

        if not config.api_key:
            raise APIKeyError("z.ai API key is required", provider="zai")

        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url or self.BASE_URL,
            timeout=config.timeout,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, TimeoutError)),
        reraise=True,
    )
    async def chat_completion(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send chat completion request to z.ai.

        Args:
            messages: Conversation messages
            model: Model to use (defaults to config.default_model)
            temperature: Sampling temperature (defaults to config.temperature)
            max_tokens: Maximum tokens to generate (defaults to config.max_tokens)
            **kwargs: Additional z.ai-specific parameters

        Returns:
            LLM response with content and metadata

        Raises:
            LLMError: If request fails
            BudgetExceededError: If budget limit reached
        """
        model = model or self.config.default_model
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        # Estimate cost and check budget
        estimated_cost = self._estimate_cost(model, len(str(messages)), max_tokens)
        self.check_budget(estimated_cost)

        start_time = time.time()

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": (msg.role if hasattr(msg, "role") else msg["role"]),
                        "content": (msg.content if hasattr(msg, "content") else msg["content"]),
                    }
                    for msg in messages
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body={"thinking": {"type": "enabled"}} if "glm-4.7" in model else {},
                **kwargs,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Calculate actual cost
            usage = LLMUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )
            cost = self._calculate_cost(model, usage)

            # Track metrics
            if self.config.track_costs:
                self._track_request(cost)

            return LLMResponse(
                id=response.id,
                model=response.model,
                content=response.choices[0].message.content or "",
                role=MessageRole.ASSISTANT,
                finish_reason=response.choices[0].finish_reason,
                usage=usage,
                provider="zai",
                cost_usd=cost,
                latency_ms=latency_ms,
                metadata={"raw_response": response.model_dump()},
            )

        except httpx.TimeoutException as e:
            raise TimeoutError(
                f"Request timed out after {self.config.timeout}s: {e}", provider="zai"
            )
        except Exception as e:
            if "rate_limit" in str(e).lower():
                raise RateLimitError(str(e), provider="zai")
            raise LLMError(f"Chat completion failed: {e}", provider="zai")

    async def stream_completion(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_stream: bool = False,
        **kwargs: Any,
    ) -> AsyncIterator[str | StreamChunk]:
        """Stream chat completion response from z.ai.

        Supports both simple string streaming and enhanced GLM-4.7 streaming
        (reasoning_content, tool_calls).

        Args:
            messages: Conversation messages
            model: Model to use (defaults to config.default_model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: Optional tool definitions for function calling
            tool_stream: If True, yield StreamChunk objects (for GLM-4.7)
            **kwargs: Additional z.ai-specific parameters

        Yields:
            str (if tool_stream=False) or StreamChunk (if tool_stream=True)
        """
        model = model or self.config.default_model
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        # Estimate cost and check budget
        estimated_cost = self._estimate_cost(model, len(str(messages)), max_tokens)
        self.check_budget(estimated_cost)

        # Build extra_body for GLM-4.7 features
        extra_body = kwargs.pop("extra_body", {})
        if "glm-4.7" in model:
            extra_body["thinking"] = {"type": "enabled"}
            if (tool_stream or tools) and tools:
                extra_body["tool_stream"] = True

        try:
            create_kwargs: dict[str, Any] = {
                "model": model,
                "messages": [
                    {
                        "role": (msg.role if hasattr(msg, "role") else msg["role"]),
                        "content": (msg.content if hasattr(msg, "content") else msg["content"]),
                    }
                    for msg in messages
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }

            if tools:
                create_kwargs["tools"] = tools

            if extra_body:
                create_kwargs["extra_body"] = extra_body

            stream = await self.client.chat.completions.create(**create_kwargs, **kwargs)

            # Track tool calls across chunks (they stream incrementally)
            accumulated_tool_calls: dict[int, dict[str, Any]] = {}

            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason

                if not tool_stream and not tools:
                    # Backward compatible mode: yield strings
                    if hasattr(delta, "content") and delta.content:
                        yield delta.content
                    continue

                # Enhanced mode: yield StreamChunk
                stream_chunk = StreamChunk(finish_reason=finish_reason)

                # Content
                if hasattr(delta, "content") and delta.content:
                    stream_chunk.content = delta.content

                # Reasoning content (GLM-4.7 thinking)
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    stream_chunk.reasoning_content = delta.reasoning_content

                # Tool calls (streaming)
                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        idx = tool_call.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": getattr(tool_call, "id", f"call_{idx}"),
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name if tool_call.function else "",
                                    "arguments": tool_call.function.arguments
                                    if tool_call.function
                                    else "",
                                },
                            }
                        else:
                            # Append arguments
                            if tool_call.function and tool_call.function.arguments:
                                accumulated_tool_calls[idx]["function"][
                                    "arguments"
                                ] += tool_call.function.arguments

                    # Include current state of tool calls
                    stream_chunk.tool_calls = list(accumulated_tool_calls.values())

                yield stream_chunk

        except httpx.TimeoutException as e:
            raise TimeoutError(
                f"Stream timed out after {self.config.timeout}s: {e}", provider="zai"
            )
        except Exception as e:
            if "rate_limit" in str(e).lower():
                raise RateLimitError(str(e), provider="zai")
            raise LLMError(f"Stream completion failed: {e}", provider="zai")

    async def validate_api_key(self) -> bool:
        """Validate z.ai API key by making a minimal request.

        Returns:
            True if API key is valid, False otherwise
        """
        try:
            await self.client.chat.completions.create(
                model=self.config.default_model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False

    def _estimate_cost(self, model: str, input_length: int, max_tokens: int) -> float:
        """Estimate cost of request.

        Args:
            model: Model name
            input_length: Approximate input length (chars)
            max_tokens: Maximum output tokens

        Returns:
            Estimated cost in USD
        """
        # Rough estimate: 4 chars per token
        input_tokens = input_length // 4

        model_key = model.replace("z-ai/", "")
        pricing = self.PRICING.get(model_key, {"input": 1.0, "output": 1.0})

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (max_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def _calculate_cost(self, model: str, usage: LLMUsage) -> float:
        """Calculate actual cost based on usage.

        Args:
            model: Model name
            usage: Token usage

        Returns:
            Cost in USD
        """
        model_key = model.replace("z-ai/", "")
        pricing = self.PRICING.get(model_key, {"input": 1.0, "output": 1.0})

        input_cost = (usage.prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (usage.completion_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost


class GLMConfig(LLMConfig):
    """Alias for GLM-specific configuration."""

    def __init__(self, api_key: str, model: str = "glm-4.7", **kwargs: Any):
        super().__init__(api_key=api_key, default_model=model, provider="zai", **kwargs)


class GLMVisionClient(ZaiClient):
    """Alias for ZAI client when used for vision tasks."""

    @property
    def total_tokens_used(self) -> int:
        # For compatibility with prime-radiant-ai usage
        return self._total_request_tokens if hasattr(self, "_total_request_tokens") else 0
