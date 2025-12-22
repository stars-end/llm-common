from __future__ import annotations

import dataclasses

from llm_common.agents import models as agent_models


@dataclasses.dataclass
class MessageHistory:
    """Manages a history of messages for a multi-turn conversation."""

    messages: list[agent_models.Message] = dataclasses.field(default_factory=list)

    def add_message(self, message: agent_models.Message) -> None:
        """Adds a message to the history."""
        self.messages.append(message)

    def __iter__(self):
        return iter(self.messages)

    def __len__(self):
        return len(self.messages)
