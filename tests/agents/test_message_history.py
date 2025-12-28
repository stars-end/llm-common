from unittest.mock import AsyncMock, MagicMock

import pytest

from llm_common.agents.message_history import Message, MessageHistory
from llm_common.core.models import LLMResponse, LLMUsage


@pytest.fixture
def mock_llm_client():
    """Fixture for a mocked LLMClient."""
    client = MagicMock()
    client.chat_completion = AsyncMock()
    return client


@pytest.fixture
def message_history(mock_llm_client):
    """Fixture for a MessageHistory instance with a mocked client."""
    return MessageHistory(llm_client=mock_llm_client)


@pytest.mark.asyncio
class TestMessageHistory:
    async def test_initial_state(self, message_history: MessageHistory):
        """Test the initial state of MessageHistory."""
        assert not message_history.has_messages()
        assert message_history._messages == []

    async def test_add_message(
        self, message_history: MessageHistory, mock_llm_client: MagicMock
    ):
        """Test adding a message."""
        mock_llm_client.chat_completion.return_value = LLMResponse(
            id="test_id",
            content="This is a summary.",
            model="test_model",
            usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            finish_reason="stop",
        )

        query = "What is the capital of France?"
        answer = "The capital of France is Paris."
        await message_history.add_message(query, answer)

        assert message_history.has_messages()
        assert len(message_history._messages) == 1
        message = message_history._messages[0]
        assert message.query == query
        assert message.answer == answer
        assert message.summary == "This is a summary."
        mock_llm_client.chat_completion.assert_called_once()

    async def test_select_relevant_messages_no_history(
        self, message_history: MessageHistory
    ):
        """Test selecting messages when history is empty."""
        messages = await message_history.select_relevant_messages("any query")
        assert messages == []

    async def test_select_relevant_messages_with_history(
        self, message_history: MessageHistory, mock_llm_client: MagicMock
    ):
        """Test selecting relevant messages with LLM."""
        # Add some messages
        summaries = ["Summary 1.", "Summary 2.", "Summary 3."]
        for i in range(3):
            message_history._messages.append(
                Message(
                    query=f"Query {i+1}",
                    answer=f"Answer {i+1}",
                    summary=summaries[i],
                )
            )

        # Mock LLM response to select messages 1 and 3
        mock_llm_client.chat_completion.return_value = LLMResponse(
            id="test_id",
            content="1, 3",
            model="test_model",
            usage=LLMUsage(prompt_tokens=50, completion_tokens=3, total_tokens=53),
            finish_reason="stop",
        )

        current_query = "A query related to 1 and 3"
        relevant_messages = await message_history.select_relevant_messages(
            current_query
        )

        assert len(relevant_messages) == 2
        assert relevant_messages[0].query == "Query 1"
        assert relevant_messages[1].query == "Query 3"
        mock_llm_client.chat_completion.assert_called_once()

    async def test_select_relevant_messages_caching(
        self, message_history: MessageHistory, mock_llm_client: MagicMock
    ):
        """Test the caching of relevance selection."""
        message_history._messages.append(
            Message(query="Query 1", answer="Answer 1", summary="Summary 1")
        )
        message_history._messages.append(
            Message(query="Query 2", answer="Answer 2", summary="Summary 2")
        )

        mock_llm_client.chat_completion.return_value = LLMResponse(
            id="test_id",
            content="1",
            model="test_model",
            usage=LLMUsage(prompt_tokens=30, completion_tokens=1, total_tokens=31),
            finish_reason="stop",
        )

        query = "A query related to 1"
        # First call - should call LLM
        result1 = await message_history.select_relevant_messages(query)
        assert len(result1) == 1
        assert result1[0].query == "Query 1"
        mock_llm_client.chat_completion.assert_called_once()

        # Second call with same query - should use cache
        result2 = await message_history.select_relevant_messages(query)
        assert result2 == result1
        mock_llm_client.chat_completion.assert_called_once()  # No new call

    def test_format_for_planning(self, message_history: MessageHistory):
        """Test formatting messages for the planning phase."""
        messages = [
            Message("Query 1", "Answer 1", "Summary 1"),
            Message("Query 2", "Answer 2", "Summary 2"),
        ]
        expected_output = (
            "Previous conversation history:\n"
            "[1] User: Query 1\n"
            "[1] Summary: Summary 1\n"
            "[2] User: Query 2\n"
            "[2] Summary: Summary 2"
        )
        assert message_history.format_for_planning(messages) == expected_output
        assert message_history.format_for_planning([]) == ""

    def test_format_for_answer(self, message_history: MessageHistory):
        """Test formatting messages for the answer generation phase."""
        messages = [
            Message("Query 1", "Answer 1"),
            Message("Query 2", "Answer 2"),
        ]
        expected_output = (
            "Relevant conversation history:\n"
            "User: Query 1\n"
            "Assistant: Answer 1\n"
            "---\n"
            "User: Query 2\n"
            "Assistant: Answer 2"
        )
        assert message_history.format_for_answer(messages) == expected_output
        assert message_history.format_for_answer([]) == ""
