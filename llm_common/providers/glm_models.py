"""GLM-4.6V specific models for vision and tool calling."""

from typing import Any, Literal

from pydantic import BaseModel


class GLMTextContent(BaseModel):
    """Text content in a message."""

    type: Literal["text"] = "text"
    text: str


class GLMImageURL(BaseModel):
    """Image URL or base64 data."""

    url: str  # Can be http(s):// or data:image/...;base64,...


class GLMImageContent(BaseModel):
    """Image content in a message."""

    type: Literal["image_url"] = "image_url"
    image_url: GLMImageURL


GLMContent = str | list[GLMTextContent | GLMImageContent]


class GLMMessage(BaseModel):
    """Message for GLM API (supports vision)."""

    role: Literal["system", "user", "assistant", "tool"]
    content: GLMContent
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class GLMToolFunction(BaseModel):
    """Function definition for a tool."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema


class GLMTool(BaseModel):
    """Tool definition for GLM."""

    type: Literal["function"] = "function"
    function: GLMToolFunction


class GLMUsage(BaseModel):
    """Token usage from GLM response."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class GLMChoice(BaseModel):
    """Single choice in GLM response."""

    index: int
    message: dict[str, Any]
    finish_reason: str


class GLMResponse(BaseModel):
    """Response from GLM chat completion."""

    id: str
    model: str
    choices: list[GLMChoice]
    usage: GLMUsage
    created: int


class GLMConfig(BaseModel):
    """Configuration for GLM client."""

    api_key: str
    base_url: str = "https://api.z.ai/api/coding/paas/v4"  # Coding plan endpoint
    default_model: str = "glm-4.6v"
    timeout: int = 60
    max_retries: int = 3

    # For browser automation scenarios
    max_tool_iterations: int = 10  # Prevent infinite tool loops
    screenshot_max_size: int = 2_000_000  # 2MB base64 limit
