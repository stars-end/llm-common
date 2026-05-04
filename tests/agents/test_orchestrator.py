from unittest.mock import MagicMock

from llm_common.agents.orchestrator import IterativeOrchestrator
from llm_common.core import DEFAULT_TEXT_MODEL


def test_iterative_orchestrator_defaults_understand_and_reflect_to_shared_text_model() -> None:
    llm_client = MagicMock()
    tool_registry = MagicMock()

    orchestrator = IterativeOrchestrator(
        llm_client=llm_client,
        tool_registry=tool_registry,
    )

    assert orchestrator.understand.model == DEFAULT_TEXT_MODEL
    assert orchestrator.reflect.model == DEFAULT_TEXT_MODEL
