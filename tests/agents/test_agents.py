"""
Unit tests for llm-common agents module.

Tests for:
- MessageHistory
- StreamEvent and run_stream
- AgentCallbacks
- Provenance (Evidence, EvidenceEnvelope, validate_citations)
- ToolContextManager

Feature-Key: affordabot-dmzy.5
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestMessageHistory:
    """Tests for MessageHistory class."""

    def test_message_creation(self) -> None:
        """Test Message dataclass creation."""
        from llm_common.agents import Message

        msg = Message(query="Hello", answer="Hi there", summary="Greeting")
        assert msg.query == "Hello"
        assert msg.answer == "Hi there"
        assert msg.summary == "Greeting"

    def test_message_default_summary(self) -> None:
        """Test Message with default empty summary."""
        from llm_common.agents import Message

        msg = Message(query="Test", answer="Response")
        assert msg.summary == ""

    def test_message_history_init(self) -> None:
        """Test MessageHistory initialization."""
        from llm_common.agents import MessageHistory

        mock_client = MagicMock()
        history = MessageHistory(mock_client)
        assert len(history._messages) == 0


class TestStreamEvent:
    """Tests for StreamEvent and run_stream."""

    def test_stream_event_creation(self) -> None:
        """Test StreamEvent dataclass creation."""
        from llm_common.agents import StreamEvent

        event = StreamEvent(type="thinking", data="Processing...")
        assert event.type == "thinking"
        assert event.data == "Processing..."

    def test_stream_event_types(self) -> None:
        """Test various StreamEvent types."""
        from llm_common.agents import StreamEvent

        types = ["thinking", "tool_call", "tool_result", "text", "sources", "error"]
        for event_type in types:
            event = StreamEvent(type=event_type, data={"test": True})
            assert event.type == event_type


class TestAgentCallbacks:
    """Tests for AgentCallbacks protocol."""

    def test_tool_call_info(self) -> None:
        """Test ToolCallInfo dataclass."""
        from llm_common.agents import ToolCallInfo

        info = ToolCallInfo(name="search", args={"query": "test"})
        assert info.name == "search"
        assert info.args == {"query": "test"}

    def test_tool_call_result(self) -> None:
        """Test ToolCallResult dataclass."""
        from llm_common.agents import ToolCallResult

        result = ToolCallResult(
            name="search",
            args={"query": "test"},
            summary="Found 5 results",
            success=True,
        )
        assert result.name == "search"
        assert result.success is True


class TestProvenance:
    """Tests for Evidence, EvidenceEnvelope, and validate_citations."""

    def test_evidence_creation(self) -> None:
        """Test Evidence dataclass creation."""
        from llm_common.agents import Evidence

        evidence = Evidence(
            kind="url",
            label="Test Source",
            url="https://example.com",
            content="Test content",
        )
        assert evidence.kind == "url"
        assert evidence.label == "Test Source"
        assert evidence.url == "https://example.com"
        assert len(evidence.id) == 36  # UUID length

    def test_evidence_default_values(self) -> None:
        """Test Evidence with default values."""
        from llm_common.agents import Evidence

        evidence = Evidence()
        assert evidence.kind == "url"
        assert evidence.label == ""
        assert evidence.derived_from == []

    def test_envelope_creation(self) -> None:
        """Test EvidenceEnvelope creation."""
        from llm_common.agents import EvidenceEnvelope

        envelope = EvidenceEnvelope(source_tool="test_tool")
        assert envelope.source_tool == "test_tool"
        assert len(envelope.evidence) == 0

    def test_envelope_add_evidence(self) -> None:
        """Test adding evidence to envelope."""
        from llm_common.agents import Evidence, EvidenceEnvelope

        envelope = EvidenceEnvelope(source_tool="test")
        evidence = Evidence(label="Test")
        envelope.add(evidence)

        assert len(envelope.evidence) == 1
        assert envelope.evidence[0].label == "Test"

    def test_envelope_get_by_id(self) -> None:
        """Test getting evidence by ID."""
        from llm_common.agents import Evidence, EvidenceEnvelope

        envelope = EvidenceEnvelope()
        evidence = Evidence(label="Test")
        envelope.add(evidence)

        found = envelope.get_by_id(evidence.id)
        assert found is not None
        assert found.id == evidence.id

    def test_envelope_get_by_id_not_found(self) -> None:
        """Test getting non-existent evidence by ID."""
        from llm_common.agents import EvidenceEnvelope

        envelope = EvidenceEnvelope()
        found = envelope.get_by_id("non-existent-id")
        assert found is None

    def test_envelope_get_urls(self) -> None:
        """Test getting all URLs from envelope."""
        from llm_common.agents import Evidence, EvidenceEnvelope

        envelope = EvidenceEnvelope()
        envelope.add(Evidence(url="https://example1.com"))
        envelope.add(Evidence(url="https://example2.com"))
        envelope.add(Evidence())  # No URL

        urls = envelope.get_urls()
        assert len(urls) == 2
        assert "https://example1.com" in urls

    def test_validate_citations_valid(self) -> None:
        """Test validate_citations with valid citations."""
        from llm_common.agents import Evidence, EvidenceEnvelope, validate_citations

        envelope = EvidenceEnvelope()
        evidence = Evidence(label="Source")
        envelope.add(evidence)

        answer = f"According to [{evidence.id}], this is true."
        is_valid, missing = validate_citations(answer, envelope)

        assert is_valid is True
        assert len(missing) == 0

    def test_validate_citations_missing(self) -> None:
        """Test validate_citations with missing citations."""
        from llm_common.agents import EvidenceEnvelope, validate_citations

        envelope = EvidenceEnvelope()
        fake_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        answer = f"According to [{fake_uuid}], this is true."

        is_valid, missing = validate_citations(answer, envelope)

        assert is_valid is False
        assert fake_uuid in missing

    def test_format_tool_result(self) -> None:
        """Test format_tool_result helper."""
        from llm_common.agents import format_tool_result

        evidence = format_tool_result(
            tool_name="search",
            url="https://example.com",
            content="Search results",
        )

        assert evidence.kind == "url"
        assert evidence.label == "search"
        assert evidence.url == "https://example.com"


class TestToolContextManager:
    """Tests for ToolContextManager."""

    def test_hash_query(self) -> None:
        """Test hash_query returns stable hash."""
        from llm_common.agents import ToolContextManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ToolContextManager(Path(tmpdir))

            hash1 = manager.hash_query("test query")
            hash2 = manager.hash_query("test query")
            hash3 = manager.hash_query("different query")

            assert hash1 == hash2
            assert hash1 != hash3
            assert len(hash1) == 12

    @pytest.mark.asyncio
    async def test_save_context(self) -> None:
        """Test saving context to disk."""
        from llm_common.agents import ToolContextManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ToolContextManager(Path(tmpdir))

            await manager.save_context(
                tool_name="test_tool",
                args={"key": "value"},
                result={"output": "test"},
                task_id="task1",
                query_id="query1",
            )

            # Check file was created
            query_dir = Path(tmpdir) / "query1"
            assert query_dir.exists()
            files = list(query_dir.glob("*.json"))
            assert len(files) == 1

            # Check pointer store persisted meta + result
            pointers_dir = Path(tmpdir) / "_pointers" / "query1"
            assert pointers_dir.exists()
            meta_files = list(pointers_dir.glob("*.meta.json"))
            result_files = list(pointers_dir.glob("*.result.json"))
            assert len(meta_files) == 1
            assert len(result_files) == 1

    def test_get_all_sources_empty(self) -> None:
        """Test get_all_sources with no sources."""
        from llm_common.agents import ToolContextManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ToolContextManager(Path(tmpdir))
            sources = manager.get_all_sources("nonexistent")
            assert sources == []

    @pytest.mark.asyncio
    async def test_select_relevant_contexts(self) -> None:
        from llm_common.agents import ToolContextManager
        from llm_common.agents.context_pointers import compute_pointer_id
        from llm_common.core import LLMClient

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ToolContextManager(Path(tmpdir))
            query_id = "query1"

            await manager.save_context(
                tool_name="tool_a",
                args={"q": "alpha"},
                result={"text": "alpha"},
                task_id="t1",
                query_id=query_id,
            )
            await manager.save_context(
                tool_name="tool_b",
                args={"q": "beta"},
                result={"text": "beta"},
                task_id="t2",
                query_id=query_id,
            )

            pointer_b = compute_pointer_id(
                tool_name="tool_b", args={"q": "beta"}, query_id=query_id, task_id="t2"
            )

            mock_client = AsyncMock(spec=LLMClient)
            mock_response = AsyncMock()
            mock_response.content = json.dumps({"pointer_ids": [pointer_b]})
            mock_client.chat_completion.return_value = mock_response

            blob = await manager.select_relevant_contexts(
                query_id=query_id, query="need beta", client=mock_client, max_selected=1
            )

            assert "beta" in blob
            assert "alpha" not in blob


# Run with: poetry run pytest tests/agents/test_agents.py -v
