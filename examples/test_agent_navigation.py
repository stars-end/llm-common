#!/usr/bin/env python3
"""Test GLM-4.6V agent's ability to navigate and fill forms."""

# ruff: noqa: E402

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_common.agents.schemas import AgentStory
from llm_common.agents.ui_smoke_agent import UISmokeAgent
from llm_common.providers import ZaiClient

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def main() -> None:
    api_key = os.environ.get("ZAI_API_KEY")
    if not api_key:
        print("❌ ZAI_API_KEY not found")
        return

    client = ZaiClient(api_key=api_key)
    agent = UISmokeAgent(llm_client=client)

    story = AgentStory(
        id="google-search-validation",
        persona="test",
        steps=[
            {
                "id": "1",
                "description": "Go to google.com and search for 'nikon cameras'",
                "validation_criteria": ["Search results for nikon cameras are visible"],
            }
        ],
    )

    print(f"🚀 Starting story: {story.id}")
    result = await agent.run_story(story)
    print(f"🏁 Story finished. Success: {result.status}")
    if result.status == "fail":
        for step_result in result.step_results:
            if step_result.errors:
                print(f"❌ Failure reason: {step_result.errors}")


if __name__ == "__main__":
    asyncio.run(main())
