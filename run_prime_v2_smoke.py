#!/usr/bin/env python3
"""
Prime Radiant V2 Smoke Test Runner
Feature-Key: bd-6sk8.6
"""

import asyncio
import sys
import os
from pathlib import Path

# Add llm-common to path
sys.path.insert(0, str(Path(__file__).parent))

from llm_common.verification.framework import (
    UnifiedVerifier,
    VerificationConfig,
    StoryCategory,
    VerificationStory,
)

async def main():
    """Run Prime Radiant V2 smoke tests."""
    
    # Configuration
    config = VerificationConfig(
        run_id="bd-6sk8.6-dev-smoke",
        artifacts_dir="/tmp/prime-wave-reports",
        base_url="https://frontend-dev-f8a3.up.railway.app",
        glm_api_key=os.environ.get("ZAI_API_KEY"),
        timeout_seconds=300
    )
    
    # Create verifier
    verifier = UnifiedVerifier(config)
    
    # Register smoke test stories
    stories = [
        VerificationStory(
            id="pr_v2_01_cockpit_load",
            name="Cockpit Shell Load",
            category=StoryCategory.USER_STORY,
            phase=1,
            requires_browser=True,
            requires_llm=True,
            glm_prompt="Validate cockpit shell is visible with chat container and no fatal errors",
            description="Load /v2 and validate cockpit shell visibility"
        ),
        VerificationStory(
            id="pr_v2_02_composer_chat",
            name="Composer Chat Flow",
            category=StoryCategory.USER_STORY,
            phase=2,
            requires_browser=True,
            requires_llm=True,
            glm_prompt="Validate message was sent and thinking state appeared",
            description="Test composer input and send flow"
        ),
        VerificationStory(
            id="pr_v2_03_first_response",
            name="First Assistant Response",
            category=StoryCategory.USER_STORY,
            phase=3,
            requires_browser=True,
            requires_llm=True,
            glm_prompt="Validate answer appeared and check for evidence/provenance surface",
            description="Validate first assistant response render behavior"
        )
    ]
    
    # Register stories
    verifier.register_stories(stories)
    
    # Run verification
    print("🚀 Starting Prime Radiant V2 smoke test...")
    report = await verifier.run_all()
    
    # Generate reports
    from llm_common.verification.report_generator import generate_markdown_report, generate_json_summary
    
    # Ensure reports directory exists
    Path(config.artifacts_dir).mkdir(parents=True, exist_ok=True)
    
    # Generate markdown report
    markdown_path = f"{config.artifacts_dir}/bd-6sk8.6-dev-smoke-report.md"
    generate_markdown_report(report, markdown_path)
    
    # Generate JSON summary
    json_path = f"{config.artifacts_dir}/bd-6sk8.6-dev-smoke-summary.json"
    generate_json_summary(report, json_path)
    
    print(f"✅ Smoke test completed. Reports generated:")
    print(f"   Markdown: {markdown_path}")
    print(f"   JSON: {json_path}")
    
    # Print summary
    print(f"\n📊 Results: {report.passed}/{report.total} passed ({report.success_rate:.1f}%)")
    print(f"🔍 Failed: {report.failed}")
    
    return report

if __name__ == "__main__":
    asyncio.run(main())