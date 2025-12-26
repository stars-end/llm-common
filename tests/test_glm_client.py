"""Tests for GLM-4.6V client."""

import json
from unittest.mock import MagicMock, patch

import pytest

from llm_common.core import LLMError, RateLimitError, TimeoutError
from llm_common.providers import GLMClient, GLMConfig


def test_glm_client_initialization():
    """Test GLMClient initializes correctly."""
    config = GLMConfig(api_key="test-key", default_model="glm-4.6v")

    client = GLMClient(config)

    assert client.config.api_key == "test-key"
    assert client.config.default_model == "glm-4.6v"
    assert client.endpoint == "https://api.z.ai/api/coding/paas/v4/chat/completions"
    assert client.get_metrics()["total_calls"] == 0
    assert client.get_metrics()["total_tokens"] == 0


def test_glm_client_custom_base_url():
    """Test GLMClient with custom base URL."""
    config = GLMConfig(
        api_key="test-key",
        default_model="glm-4.6v",
        base_url="https://custom.z.ai/api/v4",
    )

    client = GLMClient(config)

    assert client.endpoint == "https://custom.z.ai/api/v4/chat/completions"


def test_glm_client_metrics_tracking():
    """Test metrics tracking."""
    config = GLMConfig(api_key="test-key", default_model="glm-4.6v")
    client = GLMClient(config)

    # Increment manually for testing
    client._total_calls = 5
    client._total_tokens = 1234

    metrics = client.get_metrics()
    assert metrics["total_calls"] == 5
    assert metrics["total_tokens"] == 1234

    client.reset_metrics()
    metrics = client.get_metrics()
    assert metrics["total_calls"] == 0
    assert metrics["total_tokens"] == 0


@patch("llm_common.providers.glm_client.request.urlopen")
def test_glm_chat_simple(mock_urlopen):
    """Test simple chat without tools."""
    config = GLMConfig(api_key="test-key", default_model="glm-4.6v")
    client = GLMClient(config)

    # Mock response
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(
        {
            "id": "chat-123",
            "model": "glm-4.6v",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello, world!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "created": 1234567890,
        }
    ).encode("utf-8")
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    mock_urlopen.return_value = mock_response

    messages = [{"role": "user", "content": "Hello"}]
    response = client.chat(messages)

    assert response.id == "chat-123"
    assert response.model == "glm-4.6v"
    assert response.choices[0].message["content"] == "Hello, world!"
    assert response.usage.total_tokens == 15

    # Check metrics incremented
    assert client.get_metrics()["total_calls"] == 1
    assert client.get_metrics()["total_tokens"] == 15


@patch("llm_common.providers.glm_client.request.urlopen")
def test_glm_chat_with_tools(mock_urlopen):
    """Test chat with tool calling."""
    config = GLMConfig(api_key="test-key", default_model="glm-4.6v")
    client = GLMClient(config)

    # Mock response with tool call
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(
        {
            "id": "chat-456",
            "model": "glm-4.6v",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "I'll click the button for you.",
                        "tool_calls": [
                            {
                                "id": "tc_1",
                                "type": "function",
                                "function": {
                                    "name": "click_button",
                                    "arguments": '{"button_text": "Sign In"}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
            "created": 1234567890,
        }
    ).encode("utf-8")
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    mock_urlopen.return_value = mock_response

    messages = [{"role": "user", "content": "Click the sign in button"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "click_button",
                "description": "Click a button",
                "parameters": {
                    "type": "object",
                    "properties": {"button_text": {"type": "string"}},
                    "required": ["button_text"],
                },
            },
        }
    ]

    response = client.chat_with_tools(messages, tools)

    assert response["content"] == "I'll click the button for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["function"]["name"] == "click_button"
    assert json.loads(response["tool_calls"][0]["function"]["arguments"]) == {
        "button_text": "Sign In"
    }
    assert response["finish_reason"] == "tool_calls"
    assert response["usage"]["total_tokens"] == 70


@patch("llm_common.providers.glm_client.request.urlopen")
def test_glm_chat_with_vision(mock_urlopen):
    """Test chat with vision content."""
    config = GLMConfig(api_key="test-key", default_model="glm-4.6v")
    client = GLMClient(config)

    # Mock response
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(
        {
            "id": "chat-789",
            "model": "glm-4.6v",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "The button is red."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
            "created": 1234567890,
        }
    ).encode("utf-8")
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    mock_urlopen.return_value = mock_response

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What color is this button?"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,iVBORw0K..."},
                },
            ],
        }
    ]

    response = client.chat(messages)

    assert response.choices[0].message["content"] == "The button is red."
    assert response.usage.total_tokens == 110


@patch("llm_common.providers.glm_client.request.urlopen")
def test_glm_rate_limit_error(mock_urlopen):
    """Test handling of rate limit errors."""
    from urllib.error import HTTPError

    config = GLMConfig(api_key="test-key", default_model="glm-4.6v", max_retries=1)
    client = GLMClient(config)

    # Mock HTTP 429 error
    error_response = json.dumps(
        {"error": {"code": "1113", "message": "Rate limit exceeded"}}
    ).encode("utf-8")

    mock_urlopen.side_effect = HTTPError(
        "https://api.z.ai/...",
        429,
        "Too Many Requests",
        {},
        MagicMock(read=MagicMock(return_value=error_response)),
    )

    messages = [{"role": "user", "content": "test"}]

    with pytest.raises(RateLimitError) as exc_info:
        client.chat(messages)

    assert "Rate limit" in str(exc_info.value)


@patch("llm_common.providers.glm_client.request.urlopen")
def test_glm_timeout_error(mock_urlopen):
    """Test handling of timeout errors."""
    from urllib.error import URLError

    config = GLMConfig(api_key="test-key", default_model="glm-4.6v", timeout=30, max_retries=1)
    client = GLMClient(config)

    mock_urlopen.side_effect = URLError("timed out")

    messages = [{"role": "user", "content": "test"}]

    with pytest.raises(TimeoutError) as exc_info:
        client.chat(messages)

    assert "timed out" in str(exc_info.value)


@patch("llm_common.providers.glm_client.request.urlopen")
def test_glm_generic_error(mock_urlopen):
    """Test handling of generic API errors."""
    from urllib.error import HTTPError

    config = GLMConfig(api_key="test-key", default_model="glm-4.6v", max_retries=1)
    client = GLMClient(config)

    error_response = json.dumps(
        {"error": {"code": "400", "message": "Invalid request"}}
    ).encode("utf-8")

    mock_urlopen.side_effect = HTTPError(
        "https://api.z.ai/...",
        400,
        "Bad Request",
        {},
        MagicMock(read=MagicMock(return_value=error_response)),
    )

    messages = [{"role": "user", "content": "test"}]

    with pytest.raises(LLMError) as exc_info:
        client.chat(messages)

    assert "Invalid request" in str(exc_info.value)


@patch("llm_common.providers.glm_client.request.urlopen")
def test_glm_tool_result_message(mock_urlopen):
    """Test sending tool result back in conversation."""
    config = GLMConfig(api_key="test-key", default_model="glm-4.6v")
    client = GLMClient(config)

    # Mock final response after tool execution
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(
        {
            "id": "chat-final",
            "model": "glm-4.6v",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Button clicked successfully!"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 60, "completion_tokens": 10, "total_tokens": 70},
            "created": 1234567890,
        }
    ).encode("utf-8")
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    mock_urlopen.return_value = mock_response

    messages = [
        {"role": "user", "content": "Click the button"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "tc_1",
                    "function": {"name": "click_button", "arguments": '{"button_text": "OK"}'},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "tc_1",
            "name": "click_button",
            "content": "Clicked button: OK",
        },
    ]

    response = client.chat(messages)

    assert response.choices[0].message["content"] == "Button clicked successfully!"
