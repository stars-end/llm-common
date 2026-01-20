"""Unit tests for UISmokeAgent selector utilities.

Tests the selector sanitization and fallback logic.

Feature-Key: bd-s362
"""

import pytest

from llm_common.agents.ui_smoke_agent import (
    _get_input_fallback_selectors,
    _sanitize_selector,
)


class TestSanitizeSelector:
    """Tests for _sanitize_selector function."""

    def test_valid_selector_unchanged(self) -> None:
        """Valid selectors should pass through unchanged."""
        assert _sanitize_selector('[data-testid="test"]') == '[data-testid="test"]'
        assert _sanitize_selector("input.myclass") == "input.myclass"
        assert _sanitize_selector("#myid") == "#myid"

    def test_strips_whitespace(self) -> None:
        """Should strip leading/trailing whitespace."""
        assert _sanitize_selector("  .selector  ") == ".selector"

    def test_removes_surrounding_quotes(self) -> None:
        """Should remove surrounding quotes from selector."""
        assert _sanitize_selector('"input[type=text]"') == "input[type=text]"
        assert _sanitize_selector("'input[type=text]'") == "input[type=text]"

    def test_rejects_double_pipe(self) -> None:
        """Should reject selectors with invalid || but try to recover first part."""
        result = _sanitize_selector("input[placeholder='test'] || textarea")
        assert result == "input[placeholder='test']"
        assert "||" not in result

    def test_rejects_empty_before_double_pipe(self) -> None:
        """Should raise ValueError if no valid part before ||."""
        with pytest.raises(ValueError, match="Invalid selector"):
            _sanitize_selector(" || textarea")

    def test_rejects_empty_selector(self) -> None:
        """Should raise ValueError for empty selector."""
        with pytest.raises(ValueError, match="Empty selector"):
            _sanitize_selector("")

    def test_rejects_whitespace_only_selector(self) -> None:
        """Should raise ValueError for whitespace-only selector."""
        with pytest.raises(ValueError, match="Empty selector"):
            _sanitize_selector("   ")


class TestGetInputFallbackSelectors:
    """Tests for _get_input_fallback_selectors function."""

    def test_no_fallbacks_for_regular_selector(self) -> None:
        """Regular selectors should return only themselves."""
        result = _get_input_fallback_selectors(".myclass")
        assert result == [".myclass"]

    def test_input_placeholder_adds_textarea_fallback(self) -> None:
        """input[placeholder=...] should add textarea fallback."""
        selector = 'input[placeholder="Ask a question..."]'
        result = _get_input_fallback_selectors(selector)

        assert selector in result
        assert 'textarea[placeholder="Ask a question..."]' in result
        assert '[placeholder="Ask a question..."]' in result

    def test_textarea_placeholder_adds_input_fallback(self) -> None:
        """textarea[placeholder=...] should add input fallback."""
        selector = 'textarea[placeholder="Enter text..."]'
        result = _get_input_fallback_selectors(selector)

        assert selector in result
        assert 'input[placeholder="Enter text..."]' in result
        assert '[placeholder="Enter text..."]' in result

    def test_question_placeholder_adds_testid_fallback(self) -> None:
        """Placeholders with 'question' should add advisor-chat-input testid."""
        selector = 'input[placeholder="Ask a question..."]'
        result = _get_input_fallback_selectors(selector)

        assert '[data-testid="advisor-chat-input"]' in result

    def test_original_selector_first(self) -> None:
        """Original selector should be first in the list."""
        selector = 'input[placeholder="test"]'
        result = _get_input_fallback_selectors(selector)

        assert result[0] == selector


class TestSelectorPatterns:
    """Integration tests for common problematic patterns."""

    def test_llm_generated_double_pipe(self) -> None:
        """LLM sometimes generates 'selector1 || selector2'."""
        raw = 'input[placeholder="test"] || textarea[placeholder="test"]'
        sanitized = _sanitize_selector(raw)
        assert "||" not in sanitized
        assert sanitized == 'input[placeholder="test"]'

    def test_quoted_selector(self) -> None:
        """LLM sometimes wraps entire selector in quotes."""
        raw = '"input[placeholder=\\"test\\"]"'
        sanitized = _sanitize_selector(raw)
        assert not sanitized.startswith('"')
        assert not sanitized.endswith('"')

    def test_mui_textarea_fallback(self) -> None:
        """MUI TextField renders as textarea, need fallback from input."""
        selector = 'input[placeholder="Ask a question..."]'
        fallbacks = _get_input_fallback_selectors(selector)

        # Should have original + textarea + generic
        assert len(fallbacks) >= 3
        assert any("textarea" in f for f in fallbacks)
