import hashlib
from dataclasses import dataclass

from llm_common import LLMClient, LLMMessage, MessageRole


@dataclass
class Message:
    """Represents a single turn in a conversation."""
    query: str
    answer: str
    summary: str = ""


class MessageHistory:
    """Manages multi-turn conversation memory."""

    def __init__(self, llm_client: LLMClient):
        """
        Initializes the MessageHistory.

        Args:
            llm_client: An LLMClient instance for making API calls.
        """
        self._messages: list[Message] = []
        self._llm_client = llm_client
        self._relevance_cache: dict[str, list[Message]] = {}

    async def add_message(self, query: str, answer: str) -> None:
        """
        Adds a message to the history and generates a summary.

        Args:
            query: The user's query.
            answer: The assistant's answer.
        """
        summary_prompt = f"""
Summarize the following conversation turn in one sentence.
User: {query}
Assistant: {answer}
Summary:
"""
        response = await self._llm_client.chat_completion(
            messages=[LLMMessage(role=MessageRole.USER, content=summary_prompt)],
            max_tokens=50,
            temperature=0.1,
        )
        summary = response.content.strip()
        self._messages.append(Message(query=query, answer=answer, summary=summary))

    def _get_query_hash(self, query: str) -> str:
        """Generates a SHA256 hash for a given query string."""
        return hashlib.sha256(query.encode()).hexdigest()

    async def select_relevant_messages(self, current_query: str) -> list[Message]:
        """
        Selects relevant messages from history based on the current query.

        Args:
            current_query: The user's current query.

        Returns:
            A list of relevant Message objects.
        """
        if not self.has_messages():
            return []

        query_hash = self._get_query_hash(current_query)
        if query_hash in self._relevance_cache:
            return self._relevance_cache[query_hash]

        if len(self._messages) == 1:
            self._relevance_cache[query_hash] = self._messages
            return self._messages

        history_summary = "\n".join(
            f"[{i+1}] User: {msg.query}\n[{i+1}] Summary: {msg.summary}"
            for i, msg in enumerate(self._messages)
        )

        selection_prompt = f"""
Here is a list of previous conversation turns:
{history_summary}

Current user query: "{current_query}"

Which of the previous turns are relevant to the current query?
Provide a comma-separated list of numbers (e.g., "1, 3").
If none are relevant, respond with "none".
Relevant turns:
"""
        response = await self._llm_client.chat_completion(
            messages=[LLMMessage(role=MessageRole.USER, content=selection_prompt)],
            max_tokens=50,
            temperature=0.0,
        )

        content = response.content.strip().lower()
        if content == "none" or not content:
            self._relevance_cache[query_hash] = []
            return []

        try:
            indices = [int(i.strip()) - 1 for i in content.split(",") if i.strip().isdigit()]
            relevant_messages = [self._messages[i] for i in indices if 0 <= i < len(self._messages)]
        except (ValueError, IndexError):
            # If parsing fails, be conservative and return all messages
            relevant_messages = self._messages

        self._relevance_cache[query_hash] = relevant_messages
        return relevant_messages

    def format_for_planning(self, messages: list[Message]) -> str:
        """Formats messages for planning (queries and summaries)."""
        if not messages:
            return ""

        formatted_history = "\n".join(
            f"[{i+1}] User: {msg.query}\n[{i+1}] Summary: {msg.summary}"
            for i, msg in enumerate(messages)
        )
        return f"Previous conversation history:\n{formatted_history}"

    def format_for_answer(self, messages: list[Message]) -> str:
        """Formats messages for answering (queries and full answers)."""
        if not messages:
            return ""

        formatted_history = "\n---\n".join(
            f"User: {msg.query}\nAssistant: {msg.answer}" for msg in messages
        )
        return f"Relevant conversation history:\n{formatted_history}"

    def has_messages(self) -> bool:
        """Checks if there are any messages in the history."""
        return len(self._messages) > 0
