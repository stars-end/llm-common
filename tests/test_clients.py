"""Tests for LLM clients."""

import pytest

from llm_common.core import (
    DEFAULT_TEXT_MODEL,
    APIKeyError,
    BudgetExceededError,
    LLMConfig,
    LLMMessage,
    LLMUsage,
    MessageRole,
)
from llm_common.providers import DeepSeekClient, OpenRouterClient, ZaiClient


def test_deepseek_client_requires_api_key():
    """Test DeepSeekClient raises error without API key."""
    config = LLMConfig(api_key="", default_model=DEFAULT_TEXT_MODEL, provider="deepseek")

    with pytest.raises(APIKeyError):
        DeepSeekClient(config)


def test_zai_client_requires_api_key():
    """Test ZaiClient raises error without API key."""
    config = LLMConfig(api_key="", default_model="glm-4.7")

    with pytest.raises(APIKeyError):
        ZaiClient(config)


def test_openrouter_client_requires_api_key():
    """Test OpenRouterClient raises error without API key."""
    config = LLMConfig(api_key="", default_model="gpt-4")

    with pytest.raises(APIKeyError):
        OpenRouterClient(config)


def test_deepseek_client_initialization():
    """Test DeepSeekClient initializes correctly."""
    config = LLMConfig(
        api_key="test-key",
        default_model=DEFAULT_TEXT_MODEL,
        provider="deepseek",
    )

    client = DeepSeekClient(config)

    assert client.config.api_key == "test-key"
    assert client.config.default_model == DEFAULT_TEXT_MODEL
    assert client.get_total_cost() == 0.0
    assert client.get_request_count() == 0


def test_zai_client_initialization():
    """Test ZaiClient initializes correctly."""
    config = LLMConfig(api_key="test-key", default_model="glm-4.7", provider="zai")

    client = ZaiClient(config)

    assert client.config.api_key == "test-key"
    assert client.config.default_model == "glm-4.7"
    assert client.get_total_cost() == 0.0
    assert client.get_request_count() == 0


def test_openrouter_client_initialization():
    """Test OpenRouterClient initializes correctly."""
    config = LLMConfig(
        api_key="test-key",
        default_model="gpt-4",
        provider="openrouter",
        metadata={"site_url": "https://test.com"},
    )

    client = OpenRouterClient(config)

    assert client.config.api_key == "test-key"
    assert client.config.default_model == "gpt-4"
    assert client.get_total_cost() == 0.0
    assert client.get_request_count() == 0


def test_budget_check_passes():
    """Test budget check passes when under limit."""
    config = LLMConfig(
        api_key="test-key",
        default_model="glm-4.7",
        budget_limit_usd=10.0,
        provider="zai",
    )

    client = ZaiClient(config)
    # Should not raise
    client.check_budget(0.01)


def test_budget_check_fails():
    """Test budget check fails when over limit."""
    config = LLMConfig(
        api_key="test-key",
        default_model="glm-4.7",
        budget_limit_usd=0.10,
        provider="zai",
    )

    client = ZaiClient(config)

    # Simulate some spending
    client._track_request(0.05)

    # This should raise BudgetExceededError
    with pytest.raises(BudgetExceededError):
        client.check_budget(0.10)


def test_cost_tracking():
    """Test cost tracking functionality."""
    config = LLMConfig(
        api_key="test-key",
        default_model="glm-4.7",
        track_costs=True,
        provider="zai",
    )

    client = ZaiClient(config)

    # Track some requests
    client._track_request(0.01)
    client._track_request(0.02)
    client._track_request(0.03)

    assert client.get_total_cost() == 0.06
    assert client.get_request_count() == 3


def test_reset_metrics():
    """Test resetting metrics."""
    config = LLMConfig(api_key="test-key", default_model="glm-4.7", provider="zai")

    client = ZaiClient(config)

    # Track some activity
    client._track_request(0.05)

    assert client.get_total_cost() == 0.05
    assert client.get_request_count() == 1

    # Reset
    client.reset_metrics()

    assert client.get_total_cost() == 0.0
    assert client.get_request_count() == 0


def test_zai_estimate_cost():
    """Test cost estimation for z.ai."""
    config = LLMConfig(api_key="test-key", default_model="glm-4.7", provider="zai")

    client = ZaiClient(config)

    # Free tier model
    cost = client._estimate_cost("glm-4.7", 1000, 100)
    assert cost == 0.0

    # Unknown model (uses default non-free pricing)
    cost = client._estimate_cost("glm-4.7-pro", 1000, 100)
    assert cost > 0.0


def test_deepseek_estimate_cost():
    """Test cost estimation for official DeepSeek."""
    config = LLMConfig(api_key="test-key", default_model=DEFAULT_TEXT_MODEL, provider="deepseek")

    client = DeepSeekClient(config)

    cost = client._estimate_cost(DEFAULT_TEXT_MODEL, 1000, 100)
    assert cost > 0.0

    cost = client._calculate_cost(
        DEFAULT_TEXT_MODEL,
        LLMUsage(prompt_tokens=1000, completion_tokens=100, total_tokens=1100),
        prompt_cache_hit_tokens=200,
        prompt_cache_miss_tokens=800,
    )
    assert cost > 0.0


def test_openrouter_estimate_cost():
    """Test cost estimation for OpenRouter."""
    config = LLMConfig(api_key="test-key", default_model="gpt-4", provider="openrouter")

    client = OpenRouterClient(config)

    # Known model
    cost = client._estimate_cost("openai/gpt-4o-mini", 1000, 100)
    assert cost > 0.0

    # Unknown model (should use default pricing)
    cost = client._estimate_cost("unknown/model", 1000, 100)
    assert cost > 0.0


@pytest.mark.asyncio
async def test_zai_chat_completion_mock(mocker):
    """Test z.ai chat completion with mocked API."""
    config = LLMConfig(api_key="test-key", default_model="glm-4.7", provider="zai")

    client = ZaiClient(config)

    # Mock the OpenAI client response
    mock_response = mocker.MagicMock()
    mock_response.id = "test-123"
    mock_response.model = "glm-4.7"
    mock_response.choices = [
        mocker.MagicMock(message=mocker.MagicMock(content="Test response"), finish_reason="stop")
    ]
    mock_response.usage = mocker.MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
    mock_response.model_dump = lambda: {}

    # Use AsyncMock for async method
    mocker.patch.object(
        client.client.chat.completions,
        "create",
        return_value=mock_response,
        new_callable=mocker.AsyncMock,
    )

    messages = [LLMMessage(role=MessageRole.USER, content="Hello")]
    response = await client.chat_completion(messages)

    assert response.content == "Test response"
    assert response.model == "glm-4.7"
    assert response.usage.total_tokens == 30
    assert response.provider == "zai"


@pytest.mark.asyncio
async def test_deepseek_chat_completion_disables_thinking_by_default(mocker):
    """Test DeepSeek chat completion injects thinking=disabled unless overridden."""
    config = LLMConfig(api_key="test-key", default_model=DEFAULT_TEXT_MODEL, provider="deepseek")

    client = DeepSeekClient(config)

    mock_response = mocker.MagicMock()
    mock_response.id = "test-456"
    mock_response.model = DEFAULT_TEXT_MODEL
    mock_response.choices = [
        mocker.MagicMock(
            message=mocker.MagicMock(content='{"ok": true}', reasoning_content=None),
            finish_reason="stop",
        )
    ]
    mock_response.usage = mocker.MagicMock(
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        prompt_cache_hit_tokens=0,
        prompt_cache_miss_tokens=10,
        completion_tokens_details=mocker.MagicMock(reasoning_tokens=0),
    )
    mock_response.system_fingerprint = "fp-test"
    mock_response.model_dump = lambda: {}

    create_mock = mocker.AsyncMock(return_value=mock_response)
    mocker.patch.object(client.client.chat.completions, "create", create_mock)

    messages = [LLMMessage(role=MessageRole.USER, content="Return json")]
    response = await client.chat_completion(
        messages,
        response_format={"type": "json_object"},
    )

    assert response.content == '{"ok": true}'
    assert response.provider == "deepseek"
    kwargs = create_mock.call_args.kwargs
    assert kwargs["extra_body"]["thinking"] == {"type": "disabled"}
