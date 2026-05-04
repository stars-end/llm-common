"""Unit tests for UISmokeAgent selector utilities.

Tests the selector sanitization and fallback logic.

Feature-Key: bd-s362
"""

import pytest

from llm_common.agents.ui_smoke_agent import (
    _get_input_fallback_selectors,
    _is_valid_css_selector,
    _sanitize_selector,
)


class TestSanitizeSelector:
    """Tests for _sanitize_selector function."""

    def test_valid_selector_unchanged(self):
        """Valid selectors should pass through unchanged."""
        assert _sanitize_selector('[data-testid="test"]') == '[data-testid="test"]'
        assert _sanitize_selector("input.myclass") == "input.myclass"
        assert _sanitize_selector("#myid") == "#myid"

    def test_strips_whitespace(self):
        """Should strip leading/trailing whitespace."""
        assert _sanitize_selector("  .selector  ") == ".selector"

    def test_removes_surrounding_quotes(self):
        """Should remove surrounding quotes from selector."""
        assert _sanitize_selector('"input[type=text]"') == "input[type=text]"
        assert _sanitize_selector("'input[type=text]'") == "input[type=text]"

    def test_rejects_double_pipe(self):
        """Should reject selectors with invalid || but try to recover first part."""
        result = _sanitize_selector("input[placeholder='test'] || textarea")
        assert result == "input[placeholder='test']"
        assert "||" not in result

    def test_rejects_empty_before_double_pipe(self):
        """Should raise ValueError if no valid part before ||."""
        with pytest.raises(ValueError, match="Invalid selector"):
            _sanitize_selector(" || textarea")

    def test_rejects_empty_selector(self):
        """Should raise ValueError for empty selector."""
        with pytest.raises(ValueError, match="Empty selector"):
            _sanitize_selector("")

    def test_rejects_whitespace_only_selector(self):
        """Should raise ValueError for whitespace-only selector."""
        with pytest.raises(ValueError, match="Empty selector"):
            _sanitize_selector("   ")


class TestGetInputFallbackSelectors:
    """Tests for _get_input_fallback_selectors function."""

    def test_no_fallbacks_for_regular_selector(self):
        """Regular selectors should return only themselves."""
        result = _get_input_fallback_selectors(".myclass")
        assert result == [".myclass"]

    def test_input_placeholder_adds_textarea_fallback(self):
        """input[placeholder=...] should add textarea fallback."""
        selector = 'input[placeholder="Ask a question..."]'
        result = _get_input_fallback_selectors(selector)

        assert selector in result
        assert 'textarea[placeholder="Ask a question..."]' in result
        assert '[placeholder="Ask a question..."]' in result

    def test_textarea_placeholder_adds_input_fallback(self):
        """textarea[placeholder=...] should add input fallback."""
        selector = 'textarea[placeholder="Enter text..."]'
        result = _get_input_fallback_selectors(selector)

        assert selector in result
        assert 'input[placeholder="Enter text..."]' in result
        assert '[placeholder="Enter text..."]' in result

    def test_question_placeholder_adds_testid_fallback(self):
        """Placeholders with 'question' should add advisor-chat-input testid."""
        selector = 'input[placeholder="Ask a question..."]'
        result = _get_input_fallback_selectors(selector)

        assert '[data-testid="advisor-chat-input"]' in result

    def test_original_selector_first(self):
        """Original selector should be first in the list."""
        selector = 'input[placeholder="test"]'
        result = _get_input_fallback_selectors(selector)

        assert result[0] == selector


class TestSelectorPatterns:
    """Integration tests for common problematic patterns."""

    def test_llm_generated_double_pipe(self):
        """LLM sometimes generates 'selector1 || selector2'."""
        raw = 'input[placeholder="test"] || textarea[placeholder="test"]'
        sanitized = _sanitize_selector(raw)
        assert "||" not in sanitized
        assert sanitized == 'input[placeholder="test"]'

    def test_quoted_selector(self):
        """LLM sometimes wraps entire selector in quotes."""
        raw = '"input[placeholder=\\"test\\"]"'
        sanitized = _sanitize_selector(raw)
        assert not sanitized.startswith('"')
        assert not sanitized.endswith('"')

    def test_mui_textarea_fallback(self):
        """MUI TextField renders as textarea, need fallback from input."""
        selector = 'input[placeholder="Ask a question..."]'
        fallbacks = _get_input_fallback_selectors(selector)

        # Should have original + textarea + generic
        assert len(fallbacks) >= 3
        assert any("textarea" in f for f in fallbacks)


class TestNaturalLanguageRejection:
    """Tests for rejecting LLM-generated natural language instead of CSS selectors.

    Feature-Key: bd-3xsu.10
    """

    def test_rejects_placeholder_text_with_ellipsis(self):
        """Should reject 'Ask your advisor...' style placeholders."""
        with pytest.raises(ValueError, match="natural language"):
            _sanitize_selector("Ask your advisor...")

    def test_rejects_markdown_button_annotation(self):
        """Should reject '[button] Send button (paper airplane icon)'."""
        with pytest.raises(ValueError, match="natural language"):
            _sanitize_selector("[button] Send button (paper airplane icon)")

    def test_rejects_sentence_like_selector(self):
        """Should reject selectors that look like sentences."""
        with pytest.raises(ValueError, match="natural language"):
            _sanitize_selector("click the submit button")

    def test_rejects_parenthetical_icon_description(self):
        """Should reject selectors with icon descriptions in parentheses."""
        with pytest.raises(ValueError, match="natural language"):
            _sanitize_selector("button (paper airplane icon)")

    def test_valid_attribute_selector_passes(self):
        """Valid attribute selectors should still work."""
        assert _sanitize_selector('[data-testid="submit-btn"]') == '[data-testid="submit-btn"]'
        assert _sanitize_selector("input[disabled]") == "input[disabled]"
        assert _sanitize_selector("button[aria-label='close']") == "button[aria-label='close']"

    def test_valid_complex_selectors_pass(self):
        """Valid complex CSS selectors should still work."""
        assert _sanitize_selector("button.primary.large") == "button.primary.large"
        assert _sanitize_selector("#main-content > div.card") == "#main-content > div.card"
        assert _sanitize_selector("input[type='text']:focus") == "input[type='text']:focus"

    def test_pseudo_attributes_allowed(self):
        """Standard pseudo-attributes like [disabled] should be allowed."""
        assert _sanitize_selector("input[disabled]") == "input[disabled]"
        assert _sanitize_selector("option[selected]") == "option[selected]"
        assert _sanitize_selector("details[open]") == "details[open]"


class TestIsValidCssSelector:
    """Unit tests for _is_valid_css_selector helper function."""

    def test_valid_simple_selectors(self):
        """Simple valid selectors should pass."""
        assert _is_valid_css_selector("#id") is True
        assert _is_valid_css_selector(".class") is True
        assert _is_valid_css_selector("button") is True
        assert _is_valid_css_selector("input[type='text']") is True

    def test_rejects_natural_language_sentences(self):
        """Natural language sentences should be rejected."""
        assert _is_valid_css_selector("Ask your advisor...") is False
        assert _is_valid_css_selector("click the button") is False
        assert _is_valid_css_selector("Submit the form now") is False

    def test_rejects_markdown_bracket_annotations(self):
        """Markdown-style brackets like [button] should be rejected."""
        assert _is_valid_css_selector("[button] Send") is False
        assert _is_valid_css_selector("[element] something") is False

    def test_accepts_valid_attribute_selectors(self):
        """Valid CSS attribute selectors should be accepted."""
        assert _is_valid_css_selector('[data-testid="foo"]') is True
        assert _is_valid_css_selector("input[disabled]") is True
        assert _is_valid_css_selector("[href^='https']") is True

    def test_rejects_icon_descriptions(self):
        """Parenthetical icon descriptions should be rejected."""
        assert _is_valid_css_selector("button (paper airplane icon)") is False
        assert _is_valid_css_selector("div (close icon)") is False
        assert _is_valid_css_selector("span (click to submit)") is False

    def test_rejects_ellipsis(self):
        """Selectors containing ellipsis should be rejected."""
        assert _is_valid_css_selector("Ask...") is False
        assert _is_valid_css_selector("Enter text...") is False
