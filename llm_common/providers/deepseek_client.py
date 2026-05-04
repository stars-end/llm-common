"""Official DeepSeek LLM client implementation."""

import time
from collections.abc import AsyncIterator
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


class DeepSeekClient(LLMClient):
    """Official DeepSeek client using the OpenAI-compatible API."""

    BASE_URL = "https://api.deepseek.com"
    DEFAULT_MODEL = "deepseek-v4-flash"
    DEFAULT_THINKING = {"type": "disabled"}

    # Pricing per 1M tokens from DeepSeek official docs on 2026-05-04.
    PRICING = {
        "deepseek-v4-flash": {
            "input_cache_hit": 0.0028,
            "input_cache_miss": 0.14,
            "output": 0.28,
        },
        "deepseek-v4-pro": {
            "input_cache_hit": 0.003625,
            "input_cache_miss": 0.435,
            "output": 0.87,
        },
        # Compatibility aliases documented by DeepSeek.
        "deepseek-chat": {
            "input_cache_hit": 0.0028,
            "input_cache_miss": 0.14,
            "output": 0.28,
        },
        "deepseek-reasoner": {
            "input_cache_hit": 0.0028,
            "input_cache_miss": 0.14,
            "output": 0.28,
        },
    }

    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)

        if not config.api_key:
            raise APIKeyError("DeepSeek API key is required", provider="deepseek")

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
        model = model or self.config.default_model
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        estimated_cost = self._estimate_cost(model, len(str(messages)), max_tokens)
        self.check_budget(estimated_cost)

        start_time = time.time()
        extra_body = self._build_extra_body(kwargs)

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": msg.role, "content": msg.content} for msg in messages],
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=extra_body,
                **kwargs,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            usage = LLMUsage(
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
            )
            cost = self._calculate_cost(
                model,
                usage,
                prompt_cache_hit_tokens=getattr(response.usage, "prompt_cache_hit_tokens", 0) or 0,
                prompt_cache_miss_tokens=(
                    getattr(response.usage, "prompt_cache_miss_tokens", 0) or usage.prompt_tokens
                ),
            )

            if self.config.track_costs:
                self._track_request(cost)

            message = response.choices[0].message
            return LLMResponse(
                id=response.id,
                model=response.model,
                content=message.content or "",
                role=MessageRole.ASSISTANT,
                finish_reason=response.choices[0].finish_reason,
                usage=usage,
                provider="deepseek",
                cost_usd=cost,
                latency_ms=latency_ms,
                metadata={
                    "raw_response": response.model_dump(),
                    "reasoning_content": getattr(message, "reasoning_content", None),
                    "reasoning_tokens": (
                        getattr(
                            getattr(response.usage, "completion_tokens_details", None),
                            "reasoning_tokens",
                            None,
                        )
                    ),
                    "prompt_cache_hit_tokens": (
                        getattr(response.usage, "prompt_cache_hit_tokens", 0) if response.usage else 0
                    ),
                    "prompt_cache_miss_tokens": (
                        getattr(response.usage, "prompt_cache_miss_tokens", 0)
                        if response.usage
                        else 0
                    ),
                    "system_fingerprint": getattr(response, "system_fingerprint", None),
                },
            )

        except httpx.TimeoutException as e:
            raise TimeoutError(
                f"Request timed out after {self.config.timeout}s: {e}", provider="deepseek"
            )
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                raise RateLimitError(str(e), provider="deepseek")
            raise LLMError(f"Chat completion failed: {e}", provider="deepseek")

    async def stream_completion(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        model = model or self.config.default_model
        temperature = temperature if temperature is not None else self.config.temperature
        max_tokens = max_tokens or self.config.max_tokens

        estimated_cost = self._estimate_cost(model, len(str(messages)), max_tokens)
        self.check_budget(estimated_cost)

        extra_body = self._build_extra_body(kwargs)

        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": msg.role, "content": msg.content} for msg in messages],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                extra_body=extra_body,
                **kwargs,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except httpx.TimeoutException as e:
            raise TimeoutError(
                f"Stream timed out after {self.config.timeout}s: {e}", provider="deepseek"
            )
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                raise RateLimitError(str(e), provider="deepseek")
            raise LLMError(f"Stream completion failed: {e}", provider="deepseek")

    async def validate_api_key(self) -> bool:
        try:
            await self.client.chat.completions.create(
                model=self.config.default_model,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
                extra_body=self._build_extra_body({}),
            )
            return True
        except Exception:
            return False

    def _build_extra_body(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        extra_body = dict(kwargs.pop("extra_body", {}) or {})
        thinking = kwargs.pop("thinking", None)
        if thinking is not None:
            extra_body["thinking"] = thinking
        extra_body.setdefault("thinking", self.DEFAULT_THINKING)
        return extra_body

    def _estimate_cost(self, model: str, input_length: int, max_tokens: int) -> float:
        input_tokens = input_length // 4
        pricing = self.PRICING.get(
            model,
            {"input_cache_hit": 0.01, "input_cache_miss": 1.0, "output": 5.0},
        )

        input_cost = (input_tokens / 1_000_000) * pricing["input_cache_miss"]
        output_cost = (max_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def _calculate_cost(
        self,
        model: str,
        usage: LLMUsage,
        *,
        prompt_cache_hit_tokens: int = 0,
        prompt_cache_miss_tokens: int | None = None,
    ) -> float:
        pricing = self.PRICING.get(
            model,
            {"input_cache_hit": 0.01, "input_cache_miss": 1.0, "output": 5.0},
        )
        miss_tokens = (
            prompt_cache_miss_tokens
            if prompt_cache_miss_tokens is not None
            else max(usage.prompt_tokens - prompt_cache_hit_tokens, 0)
        )

        input_cost = (prompt_cache_hit_tokens / 1_000_000) * pricing["input_cache_hit"]
        input_cost += (miss_tokens / 1_000_000) * pricing["input_cache_miss"]
        output_cost = (usage.completion_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost
