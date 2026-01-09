"""Tests for UnderstandPhase."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from llm_common.agents.phases.understand import (
    Entity,
    Understanding,
    UnderstandPhase,
)
from llm_common.core import LLMResponse, LLMUsage


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock()
    client.chat_completion = AsyncMock()
    return client


class TestEntity:
    """Tests for Entity model."""

    def test_entity_creation(self):
        """Test basic entity creation."""
        entity = Entity(type="ticker", value="NVDA")
        assert entity.type == "ticker"
        assert entity.value == "NVDA"

    def test_entity_types(self):
        """Test various entity types."""
        entities = [
            Entity(type="ticker", value="AAPL"),
            Entity(type="period", value="YTD"),
            Entity(type="metric", value="P/E ratio"),
            Entity(type="comparison", value="S&P 500"),
        ]
        assert len(entities) == 4


class TestUnderstanding:
    """Tests for Understanding model."""

    def test_understanding_creation(self):
        """Test basic understanding creation."""
        understanding = Understanding(
            intent="Get NVIDIA stock price",
            entities=[Entity(type="ticker", value="NVDA")],
        )
        assert understanding.intent == "Get NVIDIA stock price"
        assert len(understanding.entities) == 1

    def test_understanding_empty_entities(self):
        """Test understanding with no entities."""
        understanding = Understanding(intent="Hello world", entities=[])
        assert understanding.entities == []


class TestUnderstandPhase:
    """Tests for UnderstandPhase."""

    @pytest.mark.asyncio
    async def test_run_extracts_intent_and_entities(self, mock_llm_client):
        """Test that run() extracts intent and entities from query."""
        # Mock response
        mock_llm_client.chat_completion.return_value = LLMResponse(
            id="test",
            model="glm-4.5-air",
            content='{"intent": "Compare NVDA P/E to S&P 500", "entities": [{"type": "ticker", "value": "NVDA"}, {"type": "metric", "value": "P/E"}, {"type": "comparison", "value": "S&P 500"}]}',
            role="assistant",
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            provider="zai",
        )

        phase = UnderstandPhase(mock_llm_client, model="glm-4.5-air")
        result = await phase.run("What's NVDA's P/E vs S&P 500?")

        assert result.intent == "Compare NVDA P/E to S&P 500"
        assert len(result.entities) == 3
        assert any(e.type == "ticker" and e.value == "NVDA" for e in result.entities)

    @pytest.mark.asyncio
    async def test_run_with_conversation_context(self, mock_llm_client):
        """Test that run() includes conversation context in prompt."""
        mock_llm_client.chat_completion.return_value = LLMResponse(
            id="test",
            model="glm-4.5-air",
            content='{"intent": "Follow up on AAPL", "entities": [{"type": "ticker", "value": "AAPL"}]}',
            role="assistant",
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            provider="zai",
        )

        phase = UnderstandPhase(mock_llm_client)
        await phase.run(
            "What about its dividend?",
            conversation_context="Previously discussed AAPL stock",
        )

        # Check that context was included in the call
        call_args = mock_llm_client.chat_completion.call_args
        messages = call_args.kwargs.get("messages", call_args[0][0] if call_args[0] else [])
        user_message = next((m for m in messages if m.role == "user"), None)
        assert user_message is not None
        assert "Previously discussed AAPL" in user_message.content

    @pytest.mark.asyncio
    async def test_run_fallback_on_error(self, mock_llm_client):
        """Test that run() returns fallback on LLM error."""
        mock_llm_client.chat_completion.side_effect = Exception("API Error")

        phase = UnderstandPhase(mock_llm_client)
        result = await phase.run("Test query")

        # Should return query as intent with no entities
        assert result.intent == "Test query"
        assert result.entities == []
