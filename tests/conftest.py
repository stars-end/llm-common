"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("ZAI_API_KEY", "test-zai-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
