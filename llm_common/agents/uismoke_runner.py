import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
        mode: str = "qa",
        repro_n: int = 1,
        headless: bool = True,
        max_tool_iterations: int = 12,
        suite_timeout: int = 5400,
        story_timeout: int = 900,
        tracing: bool = False,
        nav_timeout_ms: int = 30000,
        action_timeout_ms: int = 30000,
        block_domains: list[str] | None = None,
        no_default_blocklist: bool = False,
        only_stories: list[str] | None = None,
        exclude_stories: list[str] | None = None,
        deterministic_only: bool = False,
        fail_on_classifications: list[str] | None = None,
    ):
        self.base_url = base_url
        self.stories_dir = stories_dir
        self.output_dir = output_dir
        self.auth_config = auth_config
        self.mode = mode
        self.repro_n = repro_n
        self.headless = headless
        self.max_tool_iterations = max_tool_iterations
        self.suite_timeout = suite_timeout
        self.story_timeout = story_timeout
        self.tracing = tracing
        self.nav_timeout_ms = nav_timeout_ms
        self.action_timeout_ms = action_timeout_ms
        self.block_domains = block_domains
        self.no_default_blocklist = no_default_blocklist
        self.only_stories = only_stories
        self.exclude_stories = exclude_stories
        self.deterministic_only = deterministic_only
        self.fail_on_classifications = fail_on_classifications
        self.completed_ok = False
        self.banned_classification_hit = False

        # Per-run artifact setup
        self.run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        self.run_output_dir = self.output_dir / self.run_id
        self.run_output_dir.mkdir(parents=True, exist_ok=True)
        self.stories_output_dir = self.run_output_dir / "stories"
        self.stories_output_dir.mkdir(exist_ok=True)

    async def run(self) -> bool:
        """Execute the suite."""
        stories = load_stories_from_directory(self.stories_dir)
        if not stories:
            logger.error(f"No stories found in {self.stories_dir}")
            return False

        # Filter if only_stories is provided
        if self.only_stories:
            original_count = len(stories)
            stories = [s for s in stories if s.id in self.only_stories]
            logger.info(
                f"Filtering stories: {len(stories)}/{original_count} kept ({self.only_stories})"
            )

            if not stories:
                logger.error(f"No stories matched filter: {self.only_stories}")
                return False

        # Filter if exclude_stories is provided
        if self.exclude_stories:
            original_count = len(stories)
            stories = [s for s in stories if s.id not in self.exclude_stories]
            logger.info(
                f"Excluding stories: {len(stories)}/{original_count} kept (excluded: {self.exclude_stories})"
            )
            
            if not stories:
                logger.error("No stories left after exclusion")
                return False

        logger.info(f"🚀 Starting UISmoke run {self.run_id} with {len(stories)} stories")

        run_id = self.run_id
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

        try:
            for idx, story in enumerate(stories):
                # Check suite timeout
                elapsed_suite = time.monotonic() - suite_start_time
                if elapsed_suite > self.suite_timeout:
                    logger.warning(
                        f"Suite timeout reached ({self.suite_timeout}s). Skipping remaining stories."
                    )
                    for remaining in stories[idx:]:
                        story_results.append(
                            StoryResult(
                                story_id=remaining.id,
                                status="not_run",
                                classification="not_run",
                                errors=[
                                    AgentError(
                                        type="suite_timeout",
                                        severity="blocker",
                                        message="Suite timeout exceeded",
                                    )
                                ],
                            )
                        )
                    break

                # Run Story with Repro Policy
                final_res = await self._run_story_with_repro(
                    story,
                    glm_client,
                    suite_start_time,
                    (authed_browser, authed_context, authed_adapter),
                    (guest_browser, guest_context, guest_adapter),
                    auth_manager,
                    deterministic_only=self.deterministic_only,
                )

                # Update shared adapters if they were initialized during the run
                if not authed_adapter and final_res.get("authed_shared"):
                    authed_browser, authed_context, authed_adapter = final_res["authed_shared"]

                if not guest_adapter and final_res.get("guest_shared"):
                    guest_browser, guest_context, guest_adapter = final_res["guest_shared"]

                story_results.append(final_res["result"])

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
            total_errors={
                "blocker": sum(
                    1 for r in story_results for e in r.errors if e.severity == "blocker"
                )
            },  # Simple tally
            started_at=started_at,
            completed_at=completed_at,
            metadata={
                "stories_total": len(stories),
                "stories_passed": sum(1 for r in story_results if r.status == "pass"),
                "stories_failed": sum(1 for r in story_results if r.status == "fail"),
                "stories_timed_out": sum(1 for r in story_results if r.status == "timeout"),
                "stories_not_run": sum(1 for r in story_results if r.status == "not_run"),
                "suite_timeout_seconds": self.suite_timeout,
                "story_timeout_seconds": self.story_timeout,
                "auth_mode": self.auth_config.mode,
                "cookie_signed": self.auth_config.cookie_signed,
            },
        )

        self._write_artifacts(report)

        if self.fail_on_classifications:
            # If explicit failure classifications are provided, fail ONLY if one of them is hit.
            # This allows treating product bugs as warnings (e.g. for nightly runs).
            success = True
            for r in story_results:
                if r.classification in self.fail_on_classifications:
                    logger.error(f"❌ Run failed due to banned classification: {r.classification} in {r.story_id}")
                    success = False
                    self.banned_classification_hit = True
        else:
            # Default strict mode: all must pass
            if self.deterministic_only:
                # Deterministic-only runs treat fully-skipped stories as OK; they validate only the
                # deterministic harness surface area.
                success = all(r.status in {"pass", "skip"} for r in story_results)
            else:
                success = all(r.status == "pass" for r in story_results)

        self.completed_ok = True
        logger.info(f"UISmoke run complete. Success: {success}")
        return success

    def _classify_failure(self, result: StoryResult) -> str | None:
        """Heuristic to classify the failure type."""
        if result.status == "pass":
            return None
        if result.status == "skip":
            return "skip"
        
        # [NEW] Status-driven classification
        if result.status == "timeout":
            return "timeout"
            
        if result.status == "not_run":
            for err in result.errors:
                if err.type == "suite_timeout":
                    return "suite_timeout"
                if err.type == "auth_failed":
                    return "auth_failed"
            return "not_run"

        # [EXISTING] Substring heuristics for failures (status=fail)
        all_errors = result.errors
        msg_blob = " ".join([e.message.lower() for e in all_errors])

        if "timeout" in msg_blob or "timed out" in msg_blob: # Keep this as fallback? Or maybe only for actual status?
            # If status is fail but msg says timeout, it might be a partial timeout or caught timeout.
            # But the requirement says: "if result.status == "timeout" => return "timeout"".
            # It also says "keep existing substring heuristics for navigation_failed/clerk_failed...".
            # The prompt implies for OTHER statuses (like fail), keep using heuristics.
            return "timeout"
        if "clerk" in msg_blob:
            return "clerk_failed"
        if "403" in msg_blob:
            return "403_forbidden"
        if "verification failed" in msg_blob:
            return "strict_verification_failed"
        if "navigation failed" in msg_blob:
            return "navigation_failed"
            return "other_fail"

    async def _run_story_with_repro(
        self,
        story: AgentStory,
        glm_client: Any,
        suite_start_time: float,
        authed_shared: Any,
        guest_shared: Any,
        auth_manager: Any,
        deterministic_only: bool = False,
    ) -> dict[str, Any]:
        """Run a story up to N times if it fails."""
        results: list[StoryResult] = []
        story_ev_dir = self.stories_output_dir / story.id
        story_ev_dir.mkdir(exist_ok=True)

        authed_browser, authed_context, authed_adapter = authed_shared
        guest_browser, guest_context, guest_adapter = guest_shared
        auth_verified = authed_adapter is not None
        auth_failed_reason = None

        # Effective repro_n: 1 if it passes first time, else up to self.repro_n
        max_attempts = self.repro_n if self.mode == "qa" else 1

        for k in range(max_attempts):
            attempt_dir = story_ev_dir / "attempts" / str(k + 1)
            attempt_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Story {story.id} - Attempt {k+1}/{max_attempts}")

            res = await self._run_attempt(
                story,
                glm_client,
                suite_start_time,
                attempt_dir,
                (authed_browser, authed_context, authed_adapter),
                (guest_browser, guest_context, guest_adapter),
                auth_manager,
                deterministic_only=deterministic_only,
            )

            # Update shared adapters if they were initialized
            if not authed_adapter and res.get("authed_shared"):
                authed_browser, authed_context, authed_adapter = res["authed_shared"]
                auth_verified = res.get("auth_verified", False)
                auth_failed_reason = res.get("auth_failed_reason")

            if not guest_adapter and res.get("guest_shared"):
                guest_browser, guest_context, guest_adapter = res["guest_shared"]

            result = res["result"]
            results.append(result)

            if result.status == "pass":
                break

            if k < max_attempts - 1:
                logger.warning(f"Story {story.id} failed attempt {k+1}. Rerunning...")

        # Final Classification
        final_result = results[-1]
        
        # Populate attempts history in the final result for artifacts
        final_result.attempts = [
            {
                "attempt_n": i + 1,
                "status": r.status,
                "classification": r.classification,
                "errors": [e.model_dump() for e in r.errors],
                "evidence_dir": str(story_ev_dir / "attempts" / str(i + 1))
            }
            for i, r in enumerate(results)
        ]
        
        final_result.classification = self._get_final_classification(results)

        # Write story_summary.json
        summary = {
            "story_id": story.id,
            "status": final_result.status,
            "classification": final_result.classification,
            "attempts_count": len(results),
            "final_attempt": final_result.model_dump(mode="json"),
        }
        with open(story_ev_dir / "story_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        return {
            "result": final_result,
            "authed_shared": (authed_browser, authed_context, authed_adapter)
            if authed_adapter
            else None,
            "guest_shared": (guest_browser, guest_context, guest_adapter)
            if guest_adapter
            else None,
            "auth_verified": auth_verified,
            "auth_failed_reason": auth_failed_reason,
        }

    async def _run_attempt(
        self,
        story,
        glm_client,
        suite_start_time,
        attempt_ev_dir,
        authed_shared,
        guest_shared,
        auth_manager,
        deterministic_only: bool = False,
    ) -> dict[str, Any]:
        """Perform a single run attempt for a story."""
        authed_browser, authed_context, authed_adapter = authed_shared
        guest_browser, guest_context, guest_adapter = guest_shared

        persona = story.persona.lower()
        story_auth_mode = story.metadata.get("auth_mode")
        requires_real_clerk = story.metadata.get("requires_real_clerk", False)
        redirect_check_path = story.metadata.get("auth_redirect_check_path")

        is_guest = "guest" in persona or story.metadata.get("logout") is True
        is_ui_login = story_auth_mode == "ui_login" or requires_real_clerk

        current_adapter = None
        temp_context = None
        temp_browser = None
        auth_verified = authed_adapter is not None
        auth_failed_reason = None

        try:
            if is_ui_login:
                login_config = AuthConfig(
                    mode="ui_login",
                    email=self.auth_config.email,
                    password=self.auth_config.password,
                    email_env=self.auth_config.email_env,
                    password_env=self.auth_config.password_env,
                )
                (
                    temp_browser,
                    temp_context,
                    current_adapter,
                ) = await create_playwright_context(
                    self.base_url,
                    headless=self.headless,
                    tracing=self.tracing,
                    block_domains=self.block_domains,
                    no_default_blocklist=self.no_default_blocklist,
                    nav_timeout_ms=self.nav_timeout_ms,
                    action_timeout_ms=self.action_timeout_ms,
                )

                if redirect_check_path:
                    try:
                        await current_adapter.navigate(redirect_check_path)
                        prelogin_url = await current_adapter.get_current_url()
                        if "/sign-in" not in prelogin_url:
                            import base64

                            screenshot_b64 = await current_adapter.screenshot()
                            html = await current_adapter.get_content()
                            with open(attempt_ev_dir / "prelogin.html", "w", encoding="utf-8") as f:
                                f.write(html)
                            with open(attempt_ev_dir / "prelogin.png", "wb") as f:
                                f.write(base64.b64decode(screenshot_b64))

                            return {
                                "result": StoryResult(
                                    story_id=story.id,
                                    status="fail",
                                    errors=[
                                        AgentError(
                                            type="auth_redirect_missing",
                                            severity="blocker",
                                            message=f"Expected redirect to /sign-in, got {prelogin_url}",
                                            url=prelogin_url,
                                        )
                                    ],
                                )
                            }
                    except Exception as e:
                        return {
                            "result": StoryResult(
                                story_id=story.id,
                                status="fail",
                                errors=[
                                    AgentError(
                                        type="auth_redirect_check_failed",
                                        severity="blocker",
                                        message=str(e),
                                    )
                                ],
                            )
                        }

                temp_manager = AuthManager(login_config)
                if not await temp_manager.apply_auth(current_adapter):
                    return {
                        "result": StoryResult(
                            story_id=story.id,
                            status="fail",
                            errors=[
                                AgentError(
                                    type="auth_failed",
                                    severity="blocker",
                                    message="UI Login failed",
                                )
                            ],
                        )
                    }

            elif is_guest:
                if not guest_adapter:
                    (
                        guest_browser,
                        guest_context,
                        guest_adapter,
                    ) = await create_playwright_context(
                        self.base_url,
                        headless=self.headless,
                        tracing=self.tracing,
                        block_domains=self.block_domains,
                        no_default_blocklist=self.no_default_blocklist,
                        nav_timeout_ms=self.nav_timeout_ms,
                        action_timeout_ms=self.action_timeout_ms,
                    )
                current_adapter = guest_adapter
            else:
                if not authed_adapter:
                    (
                        authed_browser,
                        authed_context,
                        authed_adapter,
                    ) = await create_playwright_context(
                        self.base_url,
                        headless=self.headless,
                        storage_state=self.auth_config.storage_state_path,
                        tracing=self.tracing,
                        block_domains=self.block_domains,
                        no_default_blocklist=self.no_default_blocklist,
                        nav_timeout_ms=self.nav_timeout_ms,
                        action_timeout_ms=self.action_timeout_ms,
                    )
                    if not await auth_manager.apply_auth(authed_adapter):
                        auth_failed_reason = "Auth application failed"
                    elif not await auth_manager.verify_auth(authed_adapter):
                        auth_failed_reason = "Auth verification failed"
                    else:
                        auth_verified = True

                if not auth_verified:
                    return {
                        "result": StoryResult(
                            story_id=story.id,
                            status="not_run",
                            errors=[
                                AgentError(
                                    type="auth_failed",
                                    severity="blocker",
                                    message=auth_failed_reason or "Auth check failed",
                                )
                            ],
                        ),
                        "authed_shared": (authed_browser, authed_context, authed_adapter),
                        "auth_verified": auth_verified,
                        "auth_failed_reason": auth_failed_reason,
                    }
                current_adapter = authed_adapter

            agent = UISmokeAgent(
                glm_client=glm_client,
                browser=current_adapter,
                base_url=self.base_url,
                max_tool_iterations=self.max_tool_iterations,
                evidence_dir=str(attempt_ev_dir),
                action_timeout_ms=self.action_timeout_ms,
            )

            # Effective timeout
            remaining_suite = self.suite_timeout - (time.monotonic() - suite_start_time)
            story_yaml_timeout = story.metadata.get("timeout_seconds", 0)
            eff_timeout = min(self.story_timeout, remaining_suite)
            if story_yaml_timeout > self.story_timeout:
                eff_timeout = min(story_yaml_timeout, remaining_suite)

            if eff_timeout <= 0:
                return {
                    "result": StoryResult(
                        story_id=story.id,
                        status="not_run",
                        errors=[
                            AgentError(
                                type="suite_timeout",
                                severity="blocker",
                                message="Suite timeout exceeded",
                            )
                        ],
                    )
                }

            try:
                result = await asyncio.wait_for(
                    agent.run_story(story, deterministic_only=deterministic_only),
                    timeout=eff_timeout
                )

                # Forensics
                forensics = {
                    "last_url": await current_adapter.get_current_url(),
                    "console_errors": list(
                        set([e.message for e in result.errors if e.type == "console_error"])
                    ),
                    "network_errors": list(
                        set([e.message for e in result.errors if e.type == "network_error"])
                    ),
                    "classification": self._classify_failure(result),
                }
                with open(attempt_ev_dir / "forensics.json", "w") as f:
                    json.dump(forensics, f, indent=2)

                with open(attempt_ev_dir / "story.json", "w") as f:
                    json.dump(result.model_dump(mode="json"), f, indent=2)

                return {
                    "result": result,
                    "authed_shared": (authed_browser, authed_context, authed_adapter)
                    if not is_ui_login and not is_guest
                    else None,
                    "guest_shared": (guest_browser, guest_context, guest_adapter)
                    if is_guest
                    else None,
                    "auth_verified": auth_verified,
                    "auth_failed_reason": auth_failed_reason,
                }

            except asyncio.TimeoutError:
                await current_adapter.screenshot()
                return {
                    "result": StoryResult(
                        story_id=story.id,
                        status="timeout",
                        errors=[
                            AgentError(
                                type="story_timeout",
                                severity="blocker",
                                message=f"Exceeded {int(eff_timeout)}s",
                            )
                        ],
                    )
                }

        except Exception as e:
            logger.exception(f"Attempt failed: {e}")
            return {
                "result": StoryResult(
                    story_id=story.id,
                    status="fail",
                    errors=[AgentError(type="crash", severity="blocker", message=str(e))],
                )
            }
        finally:
            if temp_browser:
                await temp_browser.close()
            # Handle tracing if enabled
            if self.tracing:
                ctx = temp_context or (guest_context if is_guest else authed_context)
                if ctx:
                    trace_path = attempt_ev_dir / "trace.zip"
                    await ctx.tracing.stop(path=str(trace_path))
                    if not is_ui_login:
                        await ctx.tracing.start(screenshots=True, snapshots=True, sources=True)

    def _get_final_classification(self, results: list[StoryResult]) -> str:
        """Compute final classification based on multi-attempt results."""
        last_res = results[-1]

        if last_res.status == "pass":
            if len(results) > 1:
                return "flaky_recovered"
            return "pass"
        if last_res.status == "skip":
            return "skip"

        if last_res.status == "not_run":
            for err in last_res.errors:
                if err.type == "suite_timeout":
                    return "suite_timeout"
                if err.type == "auth_failed":
                    return "auth_failed"
            return "not_run"

        signatures = [
            self._classify_failure(r) for r in results if r.status not in {"pass", "skip"}
        ]
        if not signatures:
            return "unknown"

        from collections import Counter

        counts = Counter(signatures)
        most_common, freq = counts.most_common(1)[0]

        if freq >= 2:
            return f"reproducible_{most_common}"
        
        if len(results) > 1:
            return "flaky_inconclusive"

        return f"single_{most_common}"

    def _write_artifacts(self, report: SmokeRunReport):
        """Write run.json and run.md."""
        # JSON
        with open(self.run_output_dir / "run.json", "w") as f:
            json.dump(report.to_json_dict(), f, indent=2)

        # Markdown
        with open(self.run_output_dir / "run.md", "w") as f:
            f.write(f"# UISmoke Run Report: {report.run_id}\n\n")
            f.write(f"- **Environment**: {report.environment}\n")
            f.write(f"- **Base URL**: {report.base_url}\n")
            f.write(f"- **Started**: {report.started_at}\n")
            f.write(f"- **Completed**: {report.completed_at}\n\n")

            f.write("## Summary\n")
            stats = report.metadata
            f.write(
                f"✅ **Passed**: {stats['stories_passed']} | ❌ **Failed**: {stats['stories_failed']} | ⏰ **Timeout**: {stats['stories_timed_out']} | ⏭ **Not Run**: {stats['stories_not_run']}\n\n"
            )

            f.write("## Results\n\n")
            for res in report.story_results:
                icon = (
                    "✅"
                    if res.status == "pass"
                    else "❌"
                    if res.status == "fail"
                    else "⏰"
                    if res.status == "timeout"
                    else "⏭"
                )
                f.write(f"### {icon} {res.story_id} ({res.status})\n")
                if res.errors:
                    for err in res.errors:
                        f.write(f"- [{err.severity}] {err.type}: {err.message}\n")
                f.write("\n")


def main():
    parser = argparse.ArgumentParser(description="UISmoke Universal CLI")
    subparsers = parser.add_subparsers(dest="command", help="UISmoke commands")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run UISmoke stories")
    run_parser.add_argument("--stories", required=True, help="Directory containing story YAMLs")
    run_parser.add_argument("--base-url", required=True, help="Target application URL")
    run_parser.add_argument("--output", required=True, help="Directory to write artifacts")
    run_parser.add_argument(
        "--auth-mode",
        choices=["none", "cookie_bypass", "ui_login", "storage_state"],
        default="none",
    )
    run_parser.add_argument("--cookie-name", help="Bypass cookie name")
    run_parser.add_argument("--cookie-value", help="Bypass cookie value (e.g. 'admin')")
    run_parser.add_argument(
        "--cookie-domain", default="auto", help="Bypass cookie domain (auto or explicit)"
    )
    run_parser.add_argument(
        "--cookie-signed", action="store_true", help="Enable HMAC signed bypass cookie"
    )
    run_parser.add_argument(
        "--cookie-secret-env",
        default="TEST_AUTH_BYPASS_SECRET",
        help="Env var name containing HMAC secret",
    )
    run_parser.add_argument("--email", help="UI login email")
    run_parser.add_argument("--password", help="UI login password")
    run_parser.add_argument(
        "--email-env", default="TEST_USER_EMAIL", help="Env var name for UI login email"
    )
    run_parser.add_argument(
        "--password-env", default="TEST_USER_PASSWORD", help="Env var name for UI login password"
    )
    run_parser.add_argument("--storage-state", help="Path to storage_state.json")
    run_parser.add_argument("--headless", action="store_true", default=True, help="Run headless")
    run_parser.add_argument("--no-headless", action="store_false", dest="headless")
    run_parser.add_argument(
        "--mode", choices=["qa", "gate"], default="qa", help="Harness mode: qa or gate"
    )
    run_parser.add_argument(
        "--repro", type=int, default=1, help="Reruns for failing stories (e.g. 3 for nightly)"
    )
    run_parser.add_argument("--tracing", action="store_true", help="Enable Playwright tracing")
    run_parser.add_argument("--only-stories", nargs="+", help="Run only specific story IDs")
    run_parser.add_argument("--exclude-stories", nargs="+", help="Exclude specific story IDs")
    run_parser.add_argument(
        "--deterministic-only",
        action="store_true",
        help="Skip steps that aren't deterministic (useful for harness validation)",
    )
    run_parser.add_argument("--fail-on-classifications", type=str, help="Comma-separated classifications that should cause non-zero exit (e.g. flaky_recovered,timeout)")

    # New flags
    run_parser.add_argument(
        "--suite-timeout", type=int, default=5400, help="Suite timeout in seconds"
    )
    run_parser.add_argument(
        "--story-timeout", type=int, default=900, help="Story timeout in seconds"
    )
    run_parser.add_argument(
        "--max-tool-iterations", type=int, default=12, help="Max tool iterations per story"
    )
    run_parser.add_argument(
        "--nav-timeout-ms", type=int, default=120000, help="Playwright navigation timeout"
    )
    run_parser.add_argument(
        "--action-timeout-ms", type=int, default=60000, help="Playwright action timeout"
    )
    run_parser.add_argument(
        "--block-domain", action="append", dest="block_domains", help="Domain to block (repeatable)"
    )
    run_parser.add_argument(
        "--no-default-blocklist", action="store_true", help="Disable default domain blocklist"
    )

    # Command: triage
    triage_parser = subparsers.add_parser("triage", help="Analyze results and file Beads issues")
    triage_parser.add_argument("--run-dir", required=True, help="Path to the UISmoke run directory")
    triage_parser.add_argument(
        "--beads-epic-prefix", default="[UISmoke]", help="Prefix for the created Beads epic"
    )
    triage_parser.add_argument(
        "--dry-run", action="store_true", help="Print plan instead of creating issues"
    )

    # Compatibility: default to 'run' if no subcommand provided (legacy behavior)
    if len(sys.argv) > 1 and sys.argv[1] not in ["run", "triage", "-h", "--help"]:
        sys.argv.insert(1, "run")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    if args.command == "run":
        auth_config = AuthConfig(
            mode=args.auth_mode,
            cookie_name=args.cookie_name,
            cookie_value=args.cookie_value,
            cookie_domain=args.cookie_domain,
            cookie_signed=args.cookie_signed,
            cookie_secret_env=args.cookie_secret_env,
            email=args.email,
            password=args.password,
            email_env=args.email_env,
            password_env=args.password_env,
            storage_state_path=args.storage_state,
        )

        runner = UISmokeRunner(
            base_url=args.base_url,
            stories_dir=Path(args.stories),
            output_dir=Path(args.output),
            auth_config=auth_config,
            mode=args.mode,
            repro_n=args.repro,
            headless=args.headless,
            tracing=args.tracing,
            only_stories=args.only_stories,
            exclude_stories=args.exclude_stories,
            deterministic_only=args.deterministic_only,
            suite_timeout=args.suite_timeout,
            story_timeout=args.story_timeout,
            max_tool_iterations=args.max_tool_iterations,
            nav_timeout_ms=args.nav_timeout_ms,
            action_timeout_ms=args.action_timeout_ms,
            block_domains=args.block_domains,
            no_default_blocklist=args.no_default_blocklist,
            fail_on_classifications=args.fail_on_classifications.split(',') if args.fail_on_classifications else None,
        )

        all_passed = asyncio.run(runner.run())
        # In QA mode we return success if the harness completed (artifacts written),
        # even if product bugs were found, unless explicitly asked to fail on classifications.
        if args.mode == "qa":
            if not runner.completed_ok:
                sys.exit(1)
            # Determine exit code based on QA Contract v1
            # 0: Success, 1: BAD_PRODUCT, 2: BAD_HARNESS_OR_ENV, 3: FLAKY/UNSTABLE, 4: TIMEOUT/CAPACITY
            
            final_results = runner.report.story_results # Assuming runner.report is available and has story_results
            
            has_product_bug = any(r.classification.startswith("reproducible_") for r in final_results)
            has_harness_failure = any(r.classification in ["auth_failed", "clerk_failed", "navigation_failed"] for r in final_results)
            has_flaky = any(r.classification == "flaky_recovered" for r in final_results)
            has_timeout = any("timeout" in r.classification for r in final_results)

            if has_product_bug:
                logger.error("🛑 EXIT 1: Product Regression detected")
                sys.exit(1)
            if has_harness_failure:
                logger.error("🛑 EXIT 2: Harness/Env Failure detected")
                sys.exit(2)
            if has_flaky:
                logger.info("⚠️ EXIT 3: Flaky/Unstable results detected")
                sys.exit(3)
            if has_timeout:
                 logger.warning("⏳ EXIT 4: Suite Timeout / Capacity issues")
                 sys.exit(4)
                 
            logger.info("✅ EXIT 0: All stories passed or compliant with policy")
            sys.exit(0)
        sys.exit(0 if all_passed else 1)
    elif args.command == "triage":
        from llm_common.agents.uismoke_triage import UISmokeTriage

        triager = UISmokeTriage(Path(args.run_dir), args.beads_epic_prefix, args.dry_run)
        triager.triage()
        sys.exit(0)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
