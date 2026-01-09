"""Tests for ReflectPhase."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from llm_common.agents.phases.reflect import ReflectionResult, ReflectPhase
from llm_common.agents.phases.understand import Entity, Understanding
from llm_common.core import LLMResponse, LLMUsage


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = MagicMock()
    client.chat_completion = AsyncMock()
    return client


@pytest.fixture
def sample_understanding():
    """Create a sample Understanding for tests."""
    return Understanding(
        intent="Compare NVDA P/E ratio to S&P 500",
        entities=[
            Entity(type="ticker", value="NVDA"),
            Entity(type="metric", value="P/E ratio"),
            Entity(type="comparison", value="S&P 500"),
        ],
    )


class TestReflectionResult:
    """Tests for ReflectionResult model."""

    def test_complete_result(self):
        """Test creating a complete reflection result."""
        result = ReflectionResult(
            is_complete=True,
            reasoning="All required data gathered",
            missing_info=[],
            suggested_next_steps="",
        )
        assert result.is_complete is True
        assert result.missing_info == []

    def test_incomplete_result(self):
        """Test creating an incomplete reflection result."""
        result = ReflectionResult(
            is_complete=False,
            reasoning="Missing S&P 500 P/E data",
            missing_info=["S&P 500 P/E ratio"],
            suggested_next_steps="Fetch benchmark P/E data",
        )
        assert result.is_complete is False
        assert len(result.missing_info) == 1


class TestReflectPhase:
    """Tests for ReflectPhase."""

    @pytest.mark.asyncio
    async def test_run_returns_complete(self, mock_llm_client, sample_understanding):
        """Test that run() returns complete when data is sufficient."""
        mock_llm_client.chat_completion.return_value = LLMResponse(
            id="test",
            model="glm-4.5-air",
            content='{"is_complete": true, "reasoning": "All data gathered", "missing_info": [], "suggested_next_steps": ""}',
            role="assistant",
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            provider="zai",
        )

        phase = ReflectPhase(mock_llm_client, max_iterations=2)
        result = await phase.run(
            query="What's NVDA's P/E vs S&P 500?",
            understanding=sample_understanding,
            completed_work="✓ NVDA P/E: 45.2\n✓ S&P 500 P/E: 22.1",
            iteration=0,
        )

        assert result.is_complete is True
        assert result.missing_info == []

    @pytest.mark.asyncio
    async def test_run_returns_incomplete(self, mock_llm_client, sample_understanding):
        """Test that run() returns incomplete when data is missing."""
        mock_llm_client.chat_completion.return_value = LLMResponse(
            id="test",
            model="glm-4.5-air",
            content='{"is_complete": false, "reasoning": "Missing benchmark data", "missing_info": ["S&P 500 P/E"], "suggested_next_steps": "Fetch S&P 500 metrics"}',
            role="assistant",
            finish_reason="stop",
            usage=LLMUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            provider="zai",
        )

        phase = ReflectPhase(mock_llm_client, max_iterations=3)
        result = await phase.run(
            query="What's NVDA's P/E vs S&P 500?",
            understanding=sample_understanding,
            completed_work="✓ NVDA P/E: 45.2\n✗ S&P 500 P/E: Failed",
            iteration=0,
        )

        assert result.is_complete is False
        assert "S&P 500 P/E" in result.missing_info

    @pytest.mark.asyncio
    async def test_run_forces_complete_at_max_iterations(
        self, mock_llm_client, sample_understanding
    ):
        """Test that run() forces completion at max iterations."""
        # Don't even need to set up mock - should short-circuit
        phase = ReflectPhase(mock_llm_client, max_iterations=2)
        result = await phase.run(
            query="Test",
            understanding=sample_understanding,
            completed_work="Some work done",
            iteration=2,  # At max
        )

        assert result.is_complete is True
        assert "maximum iterations" in result.reasoning.lower()
        # LLM should not have been called
        mock_llm_client.chat_completion.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_fallback_on_error(self, mock_llm_client, sample_understanding):
        """Test that run() returns complete on LLM error (fail-safe)."""
        mock_llm_client.chat_completion.side_effect = Exception("API Error")

        phase = ReflectPhase(mock_llm_client, max_iterations=3)
        result = await phase.run(
            query="Test",
            understanding=sample_understanding,
            completed_work="Work",
            iteration=0,
        )

        # Should return complete to avoid infinite loop
        assert result.is_complete is True
        assert "failed" in result.reasoning.lower()

    def test_build_planning_guidance(self, mock_llm_client):
        """Test building planning guidance from reflection."""
        phase = ReflectPhase(mock_llm_client)

        reflection = ReflectionResult(
            is_complete=False,
            reasoning="Need more data",
            missing_info=["S&P 500 P/E", "Historical trends"],
            suggested_next_steps="Fetch benchmark and historical data",
        )

        guidance = phase.build_planning_guidance(reflection)

        assert "Need more data" in guidance
        assert "S&P 500 P/E" in guidance
        assert "Fetch benchmark" in guidance

    def test_build_planning_guidance_complete(self, mock_llm_client):
        """Test building planning guidance when complete."""
        phase = ReflectPhase(mock_llm_client)

        reflection = ReflectionResult(
            is_complete=True,
            reasoning="All data gathered",
            missing_info=[],
            suggested_next_steps="",
        )

        guidance = phase.build_planning_guidance(reflection)

        assert "All data gathered" in guidance
