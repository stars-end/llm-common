from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from llm_common.agents.context_pointers import (
    ContextPointer,
    ContextRelevanceSelector,
    FileContextPointerStore,
    compute_pointer_id,
    deterministic_summary,
)
from llm_common.core.models import LLMResponse, LLMUsage


def test_pointer_id_is_deterministic() -> None:
    args_a = {"ticker": "AAPL", "limit": 5}
    args_b = {"limit": 5, "ticker": "AAPL"}  # different ordering
    pid1 = compute_pointer_id(tool_name="tool", args=args_a, query_id="q", task_id="t")
    pid2 = compute_pointer_id(tool_name="tool", args=args_b, query_id="q", task_id="t")
    assert pid1 == pid2


def test_summary_is_deterministic_and_includes_key_args() -> None:
    summary = deterministic_summary(tool_name="web_search", args={"query": "foo", "count": 3})
    assert "web_search" in summary
    assert "query=foo" in summary
    assert "count=3" in summary


@pytest.mark.asyncio
async def test_store_roundtrip(tmp_path: Path) -> None:
    store = FileContextPointerStore(base_dir=tmp_path)
    pointer = await store.save(
        query_id="qid",
        task_id="1",
        tool_name="web_search",
        args={"query": "x"},
        result={"ok": True},
    )
    pointers = store.list(query_id="qid")
    assert len(pointers) == 1
    assert pointers[0].pointer_id == pointer.pointer_id
    assert store.load_result(pointer=pointers[0]) == {"ok": True}


@pytest.mark.asyncio
async def test_selector_parses_pointer_ids_and_caps(tmp_path: Path) -> None:
    store = FileContextPointerStore(base_dir=tmp_path)
    p1 = await store.save(query_id="qid", task_id=None, tool_name="t1", args={}, result={"a": 1})
    p2 = await store.save(query_id="qid", task_id=None, tool_name="t2", args={}, result={"a": 2})

    client = AsyncMock()
    client.chat_completion.return_value = LLMResponse(
        id="x",
        model="glm-4.5-air",
        content=f'{{"pointer_ids":["{p1.pointer_id}","{p2.pointer_id}"]}}',
        finish_reason="stop",
        usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        provider="test",
    )

    selector = ContextRelevanceSelector(client=client, max_selected=1)
    selected = await selector.select(query="q", pointers=[p1, p2])
    assert len(selected) == 1
    assert selected[0].pointer_id == p1.pointer_id


@pytest.mark.asyncio
async def test_selector_fail_closed_on_invalid_output() -> None:
    p = ContextPointer(
        pointer_id="deadbeefcafe",
        query_id="qid",
        task_id=None,
        tool_name="t",
        args={},
        created_at="now",
        summary="t",
        result_path="/tmp/x",
        source_urls=[],
    )
    client = AsyncMock()
    client.chat_completion.return_value = LLMResponse(
        id="x",
        model="glm-4.5-air",
        content="not-json",
        finish_reason="stop",
        usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        provider="test",
    )
    selector = ContextRelevanceSelector(client=client, fail_closed=True)
    selected = await selector.select(query="q", pointers=[p])
    assert selected == []


def test_store_list_handles_missing_query_dir(tmp_path: Path) -> None:
    store = FileContextPointerStore(base_dir=tmp_path)
    assert store.list(query_id="non-existent-qid") == []


@pytest.mark.asyncio
async def test_selector_handles_empty_pointers_list() -> None:
    client = AsyncMock()
    selector = ContextRelevanceSelector(client=client)
    selected = await selector.select(query="q", pointers=[])
    assert selected == []
    client.chat_completion.assert_not_called()
