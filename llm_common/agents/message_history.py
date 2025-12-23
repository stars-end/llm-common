"""Multi-turn conversation memory with LLM-based summarization.

This module provides:
- Message: A single conversation turn
- MessageHistory: Manages conversation history with LLM-powered features

Ported from dexter/src/utils/message-history.ts
"""

from __future__ import annotations

import hashlib
import dataclasses
from typing import Any, Callable, Awaitable
from datetime import datetime


@dataclasses.dataclass
class Message:
    """A single conversation turn."""
    
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = dataclasses.field(default_factory=datetime.now)
    summary: str | None = None  # LLM-generated summary
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "summary": self.summary,
            "metadata": self.metadata,
        }


@dataclasses.dataclass
class MessageHistory:
    """Manages a history of messages for multi-turn conversation.
    
    Features (ported from Dexter):
    - In-memory conversation history
    - LLM-generated summaries per turn
    - LLM-based relevance selection for context
    - Caching of relevance results by query hash
    - Separate formats for planning vs answer generation
    
    Usage:
        history = MessageHistory(llm_client=client)
        await history.add_turn("What is AAPL's revenue?", "Apple's revenue is $394B...")
        
        # For a new query, get relevant context
        relevant = await history.select_relevant_messages("Compare to MSFT")
        planning_context = history.format_for_planning(relevant)
    """
    
    messages: list[Message] = dataclasses.field(default_factory=list)
    _llm_client: Any = None
    _relevance_cache: dict[str, list[int]] = dataclasses.field(default_factory=dict)
    _max_messages: int = 50
    _summary_model: str = "gpt-4o-mini"
    
    def __post_init__(self):
        if self._relevance_cache is None:
            self._relevance_cache = {}
    
    def has_messages(self) -> bool:
        """Check if there are any messages in history."""
        return len(self.messages) > 0
    
    async def add_turn(
        self,
        query: str,
        answer: str,
        generate_summary: bool = True
    ) -> None:
        """Add a complete turn (query + answer) with auto-generated summary.
        
        Args:
            query: The user's query
            answer: The assistant's response
            generate_summary: Whether to generate LLM summary
        """
        # Add user message
        user_msg = Message(role="user", content=query)
        self.messages.append(user_msg)
        
        # Add assistant message with optional summary
        summary = None
        if generate_summary and self._llm_client:
            summary = await self._generate_summary(query, answer)
        
        assistant_msg = Message(
            role="assistant",
            content=answer,
            summary=summary
        )
        self.messages.append(assistant_msg)
        
        # Clear relevance cache when history changes
        self._relevance_cache.clear()
        
        # Trim if too long
        if len(self.messages) > self._max_messages * 2:
            self.messages = self.messages[-self._max_messages * 2:]
    
    def add_message(self, message: Message) -> None:
        """Add a single message to history (low-level API)."""
        self.messages.append(message)
        self._relevance_cache.clear()
    
    async def _generate_summary(self, query: str, answer: str) -> str:
        """Generate a concise summary of a turn using LLM."""
        if not self._llm_client:
            return f"Q: {query[:50]}... A: {answer[:100]}..."
        
        prompt = f"""Summarize this conversation turn in 1-2 sentences.
Focus on the key information exchanged.

User: {query}
Assistant: {answer}

Summary:"""
        
        try:
            if hasattr(self._llm_client, 'generate'):
                response = await self._llm_client.generate(prompt)
                return response.content if hasattr(response, 'content') else str(response)
            elif hasattr(self._llm_client, 'chat_completion'):
                from llm_common.core import LLMMessage
                response = await self._llm_client.chat_completion(
                    messages=[LLMMessage(role="user", content=prompt)],
                    temperature=0.3,
                )
                return response.content
            else:
                return f"Q: {query[:50]}... A: {answer[:100]}..."
        except Exception:
            return f"Q: {query[:50]}... A: {answer[:100]}..."
    
    async def select_relevant_messages(
        self,
        current_query: str,
        max_messages: int = 5
    ) -> list[Message]:
        """Use LLM to select relevant prior turns for the current query.
        
        Args:
            current_query: The new query to find relevant context for
            max_messages: Maximum number of messages to return
            
        Returns:
            List of relevant Message objects
        """
        if not self.messages:
            return []
        
        # Check cache
        cache_key = self._hash_query(current_query)
        if cache_key in self._relevance_cache:
            indices = self._relevance_cache[cache_key]
            return [self.messages[i] for i in indices if i < len(self.messages)]
        
        # If no LLM client, return most recent messages
        if not self._llm_client:
            recent = self.messages[-max_messages * 2:]
            return recent
        
        # Build selection prompt
        history_summary = self._build_history_summary()
        
        prompt = f"""Given the conversation history and a new query, identify which previous exchanges are relevant.

Conversation History:
{history_summary}

New Query: "{current_query}"

Return a JSON object with "relevant_indices" as a list of turn numbers (0-indexed) that are relevant.
Only include turns that provide useful context for answering the new query.
Maximum {max_messages} turns.

Example: {{"relevant_indices": [0, 2, 4]}}"""

        try:
            if hasattr(self._llm_client, 'chat_completion'):
                from llm_common.core import LLMMessage
                response = await self._llm_client.chat_completion(
                    messages=[LLMMessage(role="user", content=prompt)],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
                content = response.content
                
                import json
                data = json.loads(content)
                indices = data.get("relevant_indices", [])
                
                # Convert turn indices to message indices (each turn = 2 messages)
                msg_indices = []
                for turn_idx in indices[:max_messages]:
                    user_idx = turn_idx * 2
                    assistant_idx = turn_idx * 2 + 1
                    if user_idx < len(self.messages):
                        msg_indices.append(user_idx)
                    if assistant_idx < len(self.messages):
                        msg_indices.append(assistant_idx)
                
                # Cache result
                self._relevance_cache[cache_key] = msg_indices
                
                return [self.messages[i] for i in msg_indices]
            else:
                return self.messages[-max_messages * 2:]
        except Exception:
            return self.messages[-max_messages * 2:]
    
    def _build_history_summary(self) -> str:
        """Build a summary of conversation history for LLM selection."""
        lines = []
        turn_idx = 0
        
        i = 0
        while i < len(self.messages):
            msg = self.messages[i]
            if msg.role == "user":
                query = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                
                # Look for assistant response
                answer_summary = ""
                if i + 1 < len(self.messages) and self.messages[i + 1].role == "assistant":
                    assistant_msg = self.messages[i + 1]
                    if assistant_msg.summary:
                        answer_summary = assistant_msg.summary
                    else:
                        answer_summary = assistant_msg.content[:100] + "..."
                    i += 1
                
                lines.append(f"Turn {turn_idx}: Q: {query}")
                if answer_summary:
                    lines.append(f"         A: {answer_summary}")
                turn_idx += 1
            i += 1
        
        return "\n".join(lines)
    
    def format_for_planning(self, messages: list[Message] | None = None) -> str:
        """Format messages for planning phase (lightweight: queries + summaries only).
        
        Args:
            messages: Messages to format (defaults to all)
            
        Returns:
            Formatted string for planning context
        """
        msgs = messages if messages is not None else self.messages
        if not msgs:
            return ""
        
        lines = ["Previous conversation context:"]
        
        i = 0
        while i < len(msgs):
            msg = msgs[i]
            if msg.role == "user":
                lines.append(f"- User asked: {msg.content[:150]}")
                
                # Include summary if available
                if i + 1 < len(msgs) and msgs[i + 1].role == "assistant":
                    assistant_msg = msgs[i + 1]
                    if assistant_msg.summary:
                        lines.append(f"  Summary: {assistant_msg.summary}")
                    i += 1
            i += 1
        
        return "\n".join(lines)
    
    def format_for_answer(self, messages: list[Message] | None = None) -> str:
        """Format messages for answer generation (full: queries + complete answers).
        
        Args:
            messages: Messages to format (defaults to all)
            
        Returns:
            Formatted string for answer context
        """
        msgs = messages if messages is not None else self.messages
        if not msgs:
            return ""
        
        lines = ["Conversation history:"]
        
        for msg in msgs:
            role_label = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{role_label}: {msg.content}")
        
        return "\n".join(lines)
    
    def _hash_query(self, query: str) -> str:
        """Generate hash for query-based caching."""
        return hashlib.md5(query.encode()).hexdigest()[:16]
    
    def __iter__(self):
        return iter(self.messages)
    
    def __len__(self):
        return len(self.messages)
    
    def clear(self) -> None:
        """Clear all messages and cache."""
        self.messages.clear()
        self._relevance_cache.clear()


__all__ = [
    "Message",
    "MessageHistory",
]
