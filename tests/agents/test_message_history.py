import unittest
from unittest.mock import AsyncMock, MagicMock

from llm_common.agents.message_history import MessageHistory
from llm_common.core.models import LLMResponse, LLMUsage, MessageRole


class TestMessageHistory(unittest.IsolatedAsyncioTestCase):
    async def test_select_relevant_messages_structured(self) -> None:
        # Arrange
        mock_llm_client = MagicMock()
        mock_llm_client.chat_completion = AsyncMock()
        dummy_usage = LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)

        # Mock the summarization call in add_message
        mock_llm_client.chat_completion.side_effect = [
            LLMResponse(
                id="1",
                model="test-model",
                role=MessageRole.ASSISTANT,
                content="Summary 1",
                finish_reason="stop",
                usage=dummy_usage,
            ),
            LLMResponse(
                id="2",
                model="test-model",
                role=MessageRole.ASSISTANT,
                content="Summary 2",
                finish_reason="stop",
                usage=dummy_usage,
            ),
            LLMResponse(
                id="3",
                model="test-model",
                role=MessageRole.ASSISTANT,
                content="Summary 3",
                finish_reason="stop",
                usage=dummy_usage,
            ),
            # Mock the relevance selection call
            LLMResponse(
                id="4",
                model="test-model",
                role=MessageRole.ASSISTANT,
                content='```json\n{"relevant_turns": [1, 3]}\n```',
                finish_reason="stop",
                usage=dummy_usage,
            ),
        ]

        history = MessageHistory(llm_client=mock_llm_client)
        await history.add_message("Query 1", "Answer 1")
        await history.add_message("Query 2", "Answer 2")
        await history.add_message("Query 3", "Answer 3")

        # Act
        relevant_messages = await history.select_relevant_messages("Current Query")

        # Assert
        self.assertEqual(len(relevant_messages), 2)
        self.assertEqual(relevant_messages[0].query, "Query 1")
        self.assertEqual(relevant_messages[1].query, "Query 3")
