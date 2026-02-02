# Repo Addendum: llm-common

## Tech Stack
- **Language**: Python 3.12+
- **Build System**: Poetry
- **Purpose**: Shared LLM utilities, database schema, and agent logic.

## Development Rules
- This is a shared package used by `affordabot` and `prime-radiant-ai`.
- Changes MUST be backward compatible or coordinated across consumers.
- Use `make ci-lite` for fast local verification.
- Always use absolute imports within the package.
