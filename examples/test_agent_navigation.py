#!/usr/bin/env python3
"""Test GLM-4.6V agent's ability to navigate and fill forms."""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from llm_common import GLMClient, GLMConfig  # noqa: E402
from llm_common.agents import Story, StoryStep, UISmokeAgent  # noqa: E402

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

async def main():
    api_key = os.environ.get("ZAI_API_KEY")
    if not api_key:
        print("❌ ZAI_API_KEY not found")
        return

    client = GLMClient(config=GLMConfig(api_key=api_key))
    agent = UISmokeAgent(client=client)

    story = Story(
        name="Google Search Validation",
        steps=[
            StoryStep(
                mission="Go to google.com and search for 'nikon cameras'",
                expected_outcome="Search results for nikon cameras are visible"
            )
        ]
    )

    print(f"🚀 Starting story: {story.name}")
    result = await agent.run_story(story)
    print(f"🏁 Story finished. Success: {result.success}")
    if not result.success:
        print(f"❌ Failure reason: {result.reason}")

if __name__ == "__main__":
    asyncio.run(main())
