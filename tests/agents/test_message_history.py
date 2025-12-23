"""Unit tests for MessageHistory."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from llm_common.agents.message_history import MessageHistory, Message


class TestMessageHistory:
    """Tests for MessageHistory class."""

    def test_create_empty_history(self):
        """Test creating an empty message history."""
        history = MessageHistory()
        assert len(history) == 0
        assert list(history) == []

    def test_add_message_basic(self):
        """Test adding a basic message without LLM client."""
        history = MessageHistory()
        msg = Message(role="user", content="Hello")
        history.add_message(msg)
        assert len(history) == 1
        assert history.messages[0].content == "Hello"

    def test_iter_messages(self):
        """Test iterating over messages."""
        history = MessageHistory()
        history.add_message(Message(role="user", content="Q1"))
        history.add_message(Message(role="assistant", content="A1"))
        
        messages = list(history)
        assert len(messages) == 2
        assert messages[0].content == "Q1"
        assert messages[1].content == "A1"

    @pytest.mark.asyncio
    async def test_add_turn_with_summary(self):
        """Test adding a turn with LLM-generated summary."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "User asked about X, assistant explained Y."
        mock_client.chat_completion = AsyncMock(return_value=mock_response)
        
        history = MessageHistory(llm_client=mock_client)
        await history.add_turn(query="What is X?", answer="X is Y.")
        
        assert len(history) >= 1
        # Verify LLM was called for summary
        assert mock_client.chat_completion.called

    @pytest.mark.asyncio
    async def test_select_relevant_messages(self):
        """Test selecting relevant messages for a new query."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"relevant_indices": [0, 1]}'
        mock_client.chat_completion = AsyncMock(return_value=mock_response)
        
        history = MessageHistory(llm_client=mock_client)
        history.add_message(Message(role="user", content="Q1"))
        history.add_message(Message(role="assistant", content="A1"))
        history.add_message(Message(role="user", content="Q2"))
        history.add_message(Message(role="assistant", content="A2"))
        
        relevant = await history.select_relevant_messages("New question")
        
        # Should return some messages based on LLM selection
        assert isinstance(relevant, list)

    def test_format_for_planning(self):
        """Test formatting messages for planning prompt."""
        history = MessageHistory()
        history.add_message(Message(role="user", content="Q1"))
        history.add_message(Message(role="assistant", content="A1"))
        
        formatted = history.format_for_planning(history.messages)
        
        assert isinstance(formatted, str)
        assert "Q1" in formatted

    def test_format_for_answer(self):
        """Test formatting messages for answer generation."""
        history = MessageHistory()
        history.add_message(Message(role="user", content="First question"))
        history.add_message(Message(role="assistant", content="First answer"))
        
        formatted = history.format_for_answer(history.messages)
        
        assert isinstance(formatted, str)
        assert "First question" in formatted
        assert "First answer" in formatted

    def test_has_messages(self):
        """Test has_messages property."""
        history = MessageHistory()
        assert not history.has_messages()
        
        history.add_message(Message(role="user", content="Hi"))
        assert history.has_messages()

    def test_clear_history(self):
        """Test clearing message history."""
        history = MessageHistory()
        history.add_message(Message(role="user", content="Test"))
        assert len(history) == 1
        
        history.clear()
        assert len(history) == 0
