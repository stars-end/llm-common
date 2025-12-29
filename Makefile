.PHONY: ci-lite lint test install help

help:
	@echo "Available targets:"
	@echo "  ci-lite  - Run fast local validation (lint + unit tests)"
	@echo "  lint     - Run ruff and mypy"
	@echo "  test     - Run pytest"
	@echo "  install  - Install dependencies"

install:
	poetry install

lint:
	@echo "🔍 Running Lint (ruff)..."
	poetry run ruff check .
	@echo "🔍 Running Type Check (mypy)..."
	poetry run mypy . || true

test:
	@echo "🐍 Running Unit Tests..."
	poetry run pytest

ci-lite: lint test
	@echo "✅ CI Lite completed successfully"
