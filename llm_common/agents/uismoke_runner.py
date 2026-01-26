import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from llm_common.agents.auth import AuthConfig, AuthManager
from llm_common.agents.runtime.playwright_adapter import create_playwright_context
from llm_common.agents.schemas import AgentError, SmokeRunReport, StoryResult
from llm_common.agents.ui_smoke_agent import UISmokeAgent
from llm_common.agents.utils import load_stories_from_directory
from llm_common.providers.zai_client import GLMConfig, GLMVisionClient

logger = logging.getLogger(__name__)

class UISmokeRunner:
    """Orchestrates UISmoke execution across multiple stories and personas."""

    def __init__(
        self,
        base_url: str,
        stories_dir: Path,
        output_dir: Path,
        auth_config: AuthConfig,
        headless: bool = True,
        max_tool_iterations: int = 12,
        suite_timeout: int = 5400,
        story_timeout: int = 900,
        tracing: bool = False,
    ):
        self.base_url = base_url
        self.stories_dir = stories_dir
        self.output_dir = output_dir
        self.auth_config = auth_config
        self.headless = headless
        self.max_tool_iterations = max_tool_iterations
        self.suite_timeout = suite_timeout
        self.story_timeout = story_timeout
        self.tracing = tracing

        # Artifact setup
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.stories_output_dir = self.output_dir / "stories"
        self.stories_output_dir.mkdir(exist_ok=True)

    async def run(self) -> bool:
        """Execute the suite."""
        stories = load_stories_from_directory(self.stories_dir)
        if not stories:
            logger.error(f"No stories found in {self.stories_dir}")
            return False

        logger.info(f"🚀 Starting UISmoke run with {len(stories)} stories")

        run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        started_at = datetime.now(UTC).isoformat()

        story_results: list[StoryResult] = []
        suite_start_time = time.monotonic()

        # LLM Initialization (using ZAI_API_KEY)
        api_key = os.environ.get("ZAI_API_KEY")
        if not api_key:
            logger.error("ZAI_API_KEY required")
            return False

        glm_client = GLMVisionClient(GLMConfig(api_key=api_key))

        # Context Management
        # We'll use one 'authed' context and one 'guest' context if needed
        authed_browser = None
        authed_context = None
        authed_adapter = None

        guest_browser = None
        guest_context = None
        guest_adapter = None

        auth_manager = AuthManager(self.auth_config)
        auth_verified = False
        auth_failed_reason = None

        try:
            for idx, story in enumerate(stories):
                # Check suite timeout
                elapsed_suite = time.monotonic() - suite_start_time
                if elapsed_suite > self.suite_timeout:
                    logger.warning(f"Suite timeout reached ({self.suite_timeout}s). Skipping remaining stories.")
                    for remaining in stories[idx:]:
                        story_results.append(StoryResult(
                            story_id=remaining.id,
                            status="not_run",
                            errors=[AgentError(type="suite_timeout", severity="blocker", message="Suite timeout exceeded")]
                        ))
                    break

                persona = story.persona.lower()
                is_guest = "guest" in persona or story.metadata.get("logout") is True

                # Setup context for persona
                try:
                    if is_guest:
                        if not guest_adapter:
                            guest_browser, guest_context, guest_adapter = await create_playwright_context(
                                self.base_url, headless=self.headless, tracing=self.tracing
                            )
                        current_adapter = guest_adapter
                    else:
                        if not authed_adapter:
                            authed_browser, authed_context, authed_adapter = await create_playwright_context(
                                self.base_url,
                                headless=self.headless,
                                storage_state=self.auth_config.storage_state_path,
                                tracing=self.tracing
                            )
                            # Apply & Verify Auth Once
                            if not await auth_manager.apply_auth(authed_adapter):
                                auth_failed_reason = "Auth application failed"
                            elif not await auth_manager.verify_auth(authed_adapter):
                                auth_failed_reason = "Auth verification failed"
                            else:
                                auth_verified = True

                        if not auth_verified:
                            logger.error(f"⚠️ Skipping authed story {story.id} due to auth failure.")
                            story_results.append(StoryResult(
                                story_id=story.id,
                                status="not_run",
                                errors=[AgentError(type="auth_failed", severity="blocker", message=auth_failed_reason or "Auth check failed")]
                            ))
                            continue

                        current_adapter = authed_adapter

                    # Per-story evidence dir
                    story_ev_dir = self.stories_output_dir / story.id
                    story_ev_dir.mkdir(exist_ok=True)

                    agent = UISmokeAgent(
                        glm_client=glm_client,
                        browser=current_adapter,
                        base_url=self.base_url,
                        max_tool_iterations=self.max_tool_iterations,
                        evidence_dir=str(story_ev_dir)
                    )

                    logger.info(f"Running story: {story.id} ({persona})")
                    story_timeout = story.metadata.get("timeout_seconds", self.story_timeout)

                    try:
                        result = await asyncio.wait_for(agent.run_story(story), timeout=story_timeout)
                        story_results.append(result)
                    except asyncio.TimeoutError:
                        logger.error(f"Story {story.id} timed out after {story_timeout}s")
                        story_results.append(StoryResult(
                            story_id=story.id,
                            status="timeout",
                            errors=[AgentError(type="story_timeout", severity="blocker", message=f"Exceeded {story_timeout}s")]
                        ))
                        # Capture final state on timeout
                        await current_adapter.screenshot() # Will be in logs/evidence if handled in agent or adapter

                    # If tracing, stop and save trace for this story
                    if self.tracing:
                        ctx = guest_context if is_guest else authed_context
                        if ctx:
                            trace_path = story_ev_dir / "trace.zip"
                            await ctx.tracing.stop(path=str(trace_path))
                            # Resume for next story if needed (or we'll just have one cumulative trace if we don't start/stop correctly)
                            # Actually per tech-lead "trace.zip stored per story", so we should start/stop per story.
                            await ctx.tracing.start(screenshots=True, snapshots=True, sources=True)

                except Exception as e:
                    logger.exception(f"Unexpected error in story {story.id}")
                    story_results.append(StoryResult(
                        story_id=story.id,
                        status="fail",
                        errors=[AgentError(type="crash", severity="blocker", message=str(e))]
                    ))

        finally:
            # Cleanup
            if authed_browser:
                await authed_browser.close()
            if guest_browser:
                await guest_browser.close()
            await glm_client.close()

        # Generate Reports
        completed_at = datetime.now(UTC).isoformat()
        report = SmokeRunReport(
            run_id=run_id,
            environment=os.environ.get("ENVIRONMENT", "unknown"),
            base_url=self.base_url,
            story_results=story_results,
            total_errors={"blocker": sum(1 for r in story_results for e in r.errors if e.severity == "blocker")}, # Simple tally
            started_at=started_at,
            completed_at=completed_at,
            metadata={
                "stories_total": len(stories),
                "stories_passed": sum(1 for r in story_results if r.status == "pass"),
                "stories_failed": sum(1 for r in story_results if r.status == "fail"),
                "stories_timed_out": sum(1 for r in story_results if r.status == "timeout"),
                "stories_not_run": sum(1 for r in story_results if r.status == "not_run"),
            }
        )

        self._write_artifacts(report)

        success = all(r.status == "pass" for r in story_results)
        logger.info(f"UISmoke run complete. Success: {success}")
        return success

    def _write_artifacts(self, report: SmokeRunReport):
        """Write run.json and run.md."""
        # JSON
        with open(self.output_dir / "run.json", "w") as f:
            json.dump(report.to_json_dict(), f, indent=2)

        # Markdown
        with open(self.output_dir / "run.md", "w") as f:
            f.write(f"# UISmoke Run Report: {report.run_id}\n\n")
            f.write(f"- **Environment**: {report.environment}\n")
            f.write(f"- **Base URL**: {report.base_url}\n")
            f.write(f"- **Started**: {report.started_at}\n")
            f.write(f"- **Completed**: {report.completed_at}\n\n")

            f.write("## Summary\n")
            stats = report.metadata
            f.write(f"✅ **Passed**: {stats['stories_passed']} | ❌ **Failed**: {stats['stories_failed']} | ⏰ **Timeout**: {stats['stories_timed_out']} | ⏭ **Not Run**: {stats['stories_not_run']}\n\n")

            f.write("## Results\n\n")
            for res in report.story_results:
                icon = "✅" if res.status == "pass" else "❌" if res.status == "fail" else "⏰" if res.status == "timeout" else "⏭"
                f.write(f"### {icon} {res.story_id} ({res.status})\n")
                if res.errors:
                    for err in res.errors:
                        f.write(f"- [{err.severity}] {err.type}: {err.message}\n")
                f.write("\n")

def main():
    parser = argparse.ArgumentParser(description="UISmoke Universal Runner")
    parser.add_argument("--stories", required=True, help="Directory containing story YAMLs")
    parser.add_argument("--base-url", required=True, help="Target application URL")
    parser.add_argument("--output", required=True, help="Directory to write artifacts")
    parser.add_argument("--auth-mode", choices=["none", "cookie_bypass", "ui_login", "storage_state"], default="none")
    parser.add_argument("--cookie-name", help="Bypass cookie name")
    parser.add_argument("--cookie-value", help="Bypass cookie value")
    parser.add_argument("--email", help="UI login email")
    parser.add_argument("--password", help="UI login password")
    parser.add_argument("--storage-state", help="Path to storage_state.json")
    parser.add_argument("--headless", action="store_true", default=True, help="Run headless")
    parser.add_argument("--no-headless", action="store_false", dest="headless")
    parser.add_argument("--tracing", action="store_true", help="Enable Playwright tracing")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    auth_config = AuthConfig(
        mode=args.auth_mode,
        cookie_name=args.cookie_name,
        cookie_value=args.cookie_value,
        email=args.email,
        password=args.password,
        storage_state_path=args.storage_state
    )

    runner = UISmokeRunner(
        base_url=args.base_url,
        stories_dir=Path(args.stories),
        output_dir=Path(args.output),
        auth_config=auth_config,
        headless=args.headless,
        tracing=args.tracing
    )

    success = asyncio.run(runner.run())
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
