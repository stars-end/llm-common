.PHONY: ci-lite lint test install help regenerate-agents-md verify-agents-md check-workflow-syntax

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

regenerate-agents-md:
	@echo "🔄 Regenerating AGENTS.md..."
	@./scripts/agents-md-compile.zsh

verify-agents-md:
	@./scripts/verify-agents-md.sh

check-workflow-syntax:
	@./scripts/check-workflow-syntax.sh
