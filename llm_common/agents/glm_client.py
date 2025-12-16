"""GLM-4.6V Vision Client for Z.AI API.

This client wraps the OpenAI-compatible Z.AI API with support for:
- Vision (image input)
- Tool calling (function calling)
- Streaming (optional)
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

from .models import GLMResponse

logger = logging.getLogger(__name__)


@dataclass
class GLMConfig:
    """Configuration for GLM client."""
    api_key: str | None = None
    model: str = "glm-4.6v"
    base_url: str = "https://api.z.ai/api/paas/v4"
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: float = 120.0

    def __post_init__(self):
        if self.api_key is None:
            self.api_key = os.environ.get("ZAI_API_KEY")
        if not self.api_key:
            raise ValueError("ZAI_API_KEY not provided and not in environment")


class GLMVisionClient:
    """Client for GLM-4.6V with vision and tool calling support."""

    def __init__(self, config: GLMConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=config.timeout,
        )
        self._total_tokens = 0

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str | dict = "auto",
    ) -> GLMResponse:
        """Send chat completion request.

        Args:
            messages: List of message dicts with role/content
            tools: Optional list of tool definitions
            tool_choice: "auto", "none", or specific tool

        Returns:
            GLMResponse with content and/or tool_calls
        """
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        logger.debug(f"GLM request: {len(messages)} messages, {len(tools or [])} tools")

        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()

        # Extract response
        choice = data["choices"][0]
        message = choice["message"]

        # Track usage
        usage = data.get("usage", {})
        self._total_tokens += usage.get("total_tokens", 0)

        return GLMResponse(
            content=message.get("content"),
            tool_calls=message.get("tool_calls"),
            finish_reason=choice.get("finish_reason", "stop"),
            usage=usage,
        )

    async def chat_with_vision(
        self,
        text: str,
        image_base64: str,
        system_prompt: str | None = None,
        tools: list[dict] | None = None,
        tool_choice: str | dict = "auto",
    ) -> GLMResponse:
        """Send chat with image for vision analysis.

        Args:
            text: Text prompt describing what to do
            image_base64: Base64-encoded PNG screenshot
            system_prompt: Optional system message
            tools: Optional tool definitions
            tool_choice: Tool selection mode

        Returns:
            GLMResponse with vision analysis and/or tool calls
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Build user message with text and image
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}"
                    }
                }
            ]
        })

        return await self.chat(messages, tools=tools, tool_choice=tool_choice)

    @property
    def total_tokens_used(self) -> int:
        """Total tokens used across all requests."""
        return self._total_tokens


# Tool definitions for browser automation
BROWSER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": "Navigate to a URL path relative to the base URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "URL path like /dashboard or /advisor"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click an element by CSS selector or visible text",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "CSS selector (e.g., '#submit-btn') or text='Button Text'"
                    }
                },
                "required": ["target"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text into an input field",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for the input field"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type"
                    }
                },
                "required": ["selector", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for_element",
            "description": "Wait for an element to appear",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector to wait for"
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "description": "Max wait time in milliseconds (default: 5000)"
                    }
                },
                "required": ["selector"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_step",
            "description": "Mark the current step as complete. Call this when the step objective is achieved.",
            "parameters": {
                "type": "object",
                "properties": {
                    "notes": {
                        "type": "string",
                        "description": "Optional notes about step completion"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "report_error",
            "description": "Report an error or issue found during testing",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["ui_error", "api_error", "data_mismatch", "navigation_error", "other"],
                        "description": "Type of error"
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["blocker", "high", "medium", "low"],
                        "description": "Severity level"
                    },
                    "message": {
                        "type": "string",
                        "description": "Description of the error"
                    }
                },
                "required": ["type", "severity", "message"]
            }
        }
    }
]
