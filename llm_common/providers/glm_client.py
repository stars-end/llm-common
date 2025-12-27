"""GLM-4.6V client with vision and tool calling support.

This client targets browser automation and agentic workflows, not the base LLMClient
abstraction (which is text-only). It provides native GLM-4.6V features:
- Vision: screenshots/images in messages
- Tool calling: multi-turn function execution loops
- Direct API access: no OpenAI compatibility layer

Use this for:
- Browser automation agents (screenshot → tool call → action)
- UI testing with visual verification
- Agentic exploration workflows
"""

import json
import time
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from llm_common.core import LLMError, RateLimitError, TimeoutError
from llm_common.providers.glm_models import (
    GLMConfig,
    GLMResponse,
)


class GLMClient:
    """GLM-4.6V client for vision + tool calling.

    Example:
        ```python
        from llm_common import GLMClient, GLMConfig

        config = GLMConfig(api_key="...")
        client = GLMClient(config)

        # Vision + tool calling
        response = client.chat_with_tools(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Click the login button"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
                ]
            }],
            tools=[{
                "type": "function",
                "function": {
                    "name": "click_button",
                    "description": "Click a button on the page",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "button_text": {"type": "string"}
                        },
                        "required": ["button_text"]
                    }
                }
            }]
        )

        if response["tool_calls"]:
            for tc in response["tool_calls"]:
                print(f"Tool: {tc['function']['name']}")
                print(f"Args: {tc['function']['arguments']}")
        ```
    """

    def __init__(self, config: GLMConfig) -> None:
        """Initialize GLM client.

        Args:
            config: GLM configuration with API key and settings
        """
        self.config = config
        self.endpoint = f"{config.base_url.rstrip('/')}/chat/completions"
        self._total_calls = 0
        self._total_tokens = 0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, TimeoutError)),
        reraise=True,
    )
    def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> GLMResponse:
        """Send chat completion request (no tools).

        Args:
            messages: List of message dicts with role + content
            model: Model to use (defaults to config.default_model)
            temperature: Sampling temperature (0-1)
            max_tokens: Max tokens to generate
            **kwargs: Additional GLM parameters

        Returns:
            GLM response with choices and usage

        Raises:
            LLMError: If request fails
            RateLimitError: If rate limited
            TimeoutError: If request times out
        """
        return self._call_api(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=None,
            **kwargs,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, TimeoutError)),
        reraise=True,
    )
    def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tool_choice: str = "auto",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send chat request with tool calling enabled.

        Args:
            messages: List of message dicts
            tools: List of tool definitions (GLM function schema)
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Max tokens
            tool_choice: "auto", "required", or specific function name
            **kwargs: Additional parameters

        Returns:
            Dict with:
                - content: str (assistant's text response)
                - tool_calls: list[dict] | None (tool calls if any)
                - usage: dict (token counts)
                - raw: GLMResponse (full response)

        Raises:
            LLMError: If request fails
        """
        response = self._call_api(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            **kwargs,
        )

        choice = response.choices[0]
        msg = choice.message

        return {
            "content": msg.get("content", ""),
            "tool_calls": msg.get("tool_calls"),
            "finish_reason": choice.finish_reason,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            "raw": response,
        }

    def _call_api(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
        **kwargs: Any,
    ) -> GLMResponse:
        """Internal method to call GLM API.

        Args:
            messages: Message list
            model: Model name
            temperature: Temperature
            max_tokens: Max tokens
            tools: Optional tool definitions
            tool_choice: Tool choice strategy
            **kwargs: Additional params

        Returns:
            Parsed GLM response

        Raises:
            LLMError: On API errors
            RateLimitError: On rate limit
            TimeoutError: On timeout
        """
        model = model or self.config.default_model

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        payload.update(kwargs)

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.endpoint,
            data=data,
            headers=headers,
            method="POST",
        )

        time.time()

        try:
            with request.urlopen(req, timeout=self.config.timeout) as resp:
                body = resp.read().decode("utf-8")
                parsed = json.loads(body)

                # Track metrics
                self._total_calls += 1
                if "usage" in parsed:
                    self._total_tokens += parsed["usage"].get("total_tokens", 0)

                return GLMResponse(**parsed)

        except HTTPError as e:
            error_body = e.read().decode("utf-8")
            try:
                error_data = json.loads(error_body)
                error_msg = error_data.get("error", {}).get("message", str(e))
            except json.JSONDecodeError:
                error_msg = error_body

            if e.code == 429:
                raise RateLimitError(f"GLM rate limit: {error_msg}", provider="glm")
            else:
                raise LLMError(f"GLM API error ({e.code}): {error_msg}", provider="glm")

        except URLError as e:
            if "timed out" in str(e).lower():
                raise TimeoutError(
                    f"GLM request timed out after {self.config.timeout}s",
                    provider="glm",
                )
            raise LLMError(f"GLM connection error: {e}", provider="glm")

        except Exception as e:
            raise LLMError(f"GLM request failed: {e}", provider="glm")

    def get_metrics(self) -> dict[str, int]:
        """Get client usage metrics.

        Returns:
            Dict with total_calls and total_tokens
        """
        return {
            "total_calls": self._total_calls,
            "total_tokens": self._total_tokens,
        }

    def reset_metrics(self) -> None:
        """Reset usage metrics."""
        self._total_calls = 0
        self._total_tokens = 0
