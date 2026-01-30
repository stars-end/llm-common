import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Protocol

from llm_common.agents.schemas import AgentError, AgentStory, StepResult, StoryResult
from llm_common.core import LLMClient, LLMMessage, MessageRole

logger = logging.getLogger(__name__)


def _sanitize_error(error: AgentError) -> AgentError:
    """Redact secrets in error messages."""
    error.message = re.sub(r"\{\{ENV:[A-Za-z0-9_]+\}\}", "[REDACTED]", error.message)
    return error


def _sanitize_selector(selector: str) -> str:
    """Sanitize and validate a CSS selector.

    Fixes common issues from LLM-generated selectors:
    - Removes invalid '||' (not valid CSS)
    - Strips quotes that might cause parsing issues
    - Normalizes whitespace

    Args:
        selector: Raw selector string from LLM

    Returns:
        Sanitized selector

    Raises:
        ValueError: If selector contains invalid patterns that can't be fixed
    """
    if not selector:
        raise ValueError("Empty selector")

    # Strip and normalize whitespace
    selector = selector.strip()

    # Check for empty after stripping
    if not selector:
        raise ValueError("Empty selector")

    # Reject selectors with invalid || operator (common LLM mistake)
    if "||" in selector:
        # Try to extract a valid selector before the ||
        parts = selector.split("||")
        valid_part = parts[0].strip()
        if valid_part:
            logger.warning(f"Selector contained '||', using first part: {valid_part}")
            return _sanitize_selector(valid_part)
        raise ValueError(f"Invalid selector contains '||': {selector}")

    # Remove surrounding quotes if present
    if (selector.startswith('"') and selector.endswith('"')) or (
        selector.startswith("'") and selector.endswith("'")
    ):
        selector = selector[1:-1]

    return selector


def _get_input_fallback_selectors(selector: str) -> list[str]:
    """Generate fallback selectors for input fields.

    If selector targets input[placeholder=...], also try textarea[placeholder=...]
    and generic [placeholder=...].

    Args:
        selector: Original selector

    Returns:
        List of selectors to try in order
    """
    selectors = [selector]

    # If selector uses input[placeholder=...], add fallbacks
    placeholder_match = re.search(
        r'input\[placeholder[=~\^*$|]*["\']([^"\']+)["\']', selector, re.IGNORECASE
    )
    if placeholder_match:
        placeholder_value = placeholder_match.group(1)
        # Add textarea variant
        selectors.append(f'textarea[placeholder="{placeholder_value}"]')
        # Add generic variant (matches any element with placeholder)
        selectors.append(f'[placeholder="{placeholder_value}"]')
        # Add data-testid variant if placeholder contains recognizable pattern
        if "ask" in placeholder_value.lower() or "question" in placeholder_value.lower():
            selectors.append('[data-testid="advisor-chat-input"]')

    # If selector targets textarea, add input fallback
    textarea_match = re.search(
        r'textarea\[placeholder[=~\^*$|]*["\']([^"\']+)["\']', selector, re.IGNORECASE
    )
    if textarea_match:
        placeholder_value = textarea_match.group(1)
        selectors.append(f'input[placeholder="{placeholder_value}"]')
        selectors.append(f'[placeholder="{placeholder_value}"]')

    return selectors


class BrowserAdapter(Protocol):
    """Protocol for browser interaction."""

    async def navigate(self, path: str) -> None:
        ...

    async def click(self, target: str) -> None:
        ...

    async def click_portal(self, target: str) -> None:
        ...

    async def type_text(self, selector: str, text: str) -> None:
        ...

    async def screenshot(self) -> str:
        ...  # Base64 string

    async def get_console_errors(self) -> list[str]:
        ...

    async def get_network_errors(self) -> list[dict[str, Any]]:
        ...

    async def wait_for_selector(self, selector: str, timeout_ms: int = 5000) -> None:
        ...

    async def get_content(self) -> str:
        ...

    async def get_text(self, selector: str) -> str:
        ...

    async def close(self) -> None:
        ...

    async def frame_click(self, frame_selector: str, target: str) -> None:
        ...

    async def frame_type_text(self, frame_selector: str, selector: str, text: str) -> None:
        ...

    async def frame_wait_for_selector(self, frame_selector: str, selector: str, timeout_ms: int = 5000) -> None:
        ...


class UISmokeAgent:
    """Agent that executes UI smoke tests using vision + tool calling."""

    def __init__(
        self,
        glm_client: LLMClient,
        browser: BrowserAdapter,
        base_url: str,
        max_tool_iterations: int = 10,
        evidence_dir: str | None = None,
        action_timeout_ms: int = 10000,
    ):
        """Initialize UI Smoke Agent.

        Args:
            glm_client: LLM client (must support vision)
            browser: Adapter for browser interactions
            base_url: Base URL for relative navigation
            max_tool_iterations: Max actions per step
            evidence_dir: Directory to save step-completion screenshots
            action_timeout_ms: Default timeout for actions in ms
        """
        self.llm = glm_client
        self.browser = browser
        self.base_url = base_url
        self.max_tool_iterations = max_tool_iterations
        self.evidence_dir = Path(evidence_dir) if evidence_dir else None
        self.action_timeout_ms = action_timeout_ms

        if self.evidence_dir:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def _substitute_vars(self, text: str) -> str:
        """Substitute {{ENV:VAR_NAME}} from environment."""
        if not isinstance(text, str):
            return text

        def replacer(match):
            var_name = match.group(1)
            val = os.environ.get(var_name)
            if val is None:
                raise ValueError(f"Missing environment variable: {var_name}")
            return val

        try:
            return re.sub(r"\{\{ENV:([A-Za-z0-9_]+)\}\}", replacer, text)
        except ValueError as e:
            # We'll handle this in higher level
            raise e

    def _redact_secrets(self, text: str) -> str:
        """Redact {{ENV:VAR_NAME}} patterns from logs/artifacts."""
        if not isinstance(text, str):
            return text
        return re.sub(r"\{\{ENV:[A-Za-z0-9_]+\}\}", "[REDACTED]", text)

    async def _execute_deterministic_step(
        self, step_data: dict[str, Any], actions_taken: list[dict[str, Any]]
    ) -> bool:
        """Execute structured steps deterministically (no LLM).

        Supports both:
        - Keyed form: {"navigate": "/path"}, {"click": "#id"}, {"type": "text", "selector": "#id"}
        - Action form: {"action": "wait_for_selector", "selector": "...", "timeout": 10000, "optional": true}
        """
        optional = bool(step_data.get("optional", False))

        def _record(tool: str, args: dict[str, Any]) -> None:
            actions_taken.append(
                {"tool": tool, "args": args, "deterministic": True, "optional": optional}
            )

        # 1) Keyed form
        if "navigate" in step_data:
            raw_path = step_data["navigate"]
            logger.info(f"  ⚡ Deterministic Navigate: {self._redact_secrets(raw_path)}")
            path = self._substitute_vars(raw_path)
            await self.browser.navigate(path)
            _record("navigate", {"path": self._redact_secrets(path)})
            return True

        if "click" in step_data:
            raw_target = step_data["click"]
            logger.info(f"  ⚡ Deterministic Click: {self._redact_secrets(raw_target)}")
            target = self._substitute_vars(raw_target)
            
            # BEAD-1.3: MUI Portal detection
            if "li[data-value=" in target.lower():
                await self.browser.click_portal(_sanitize_selector(target))
                _record("click_portal", {"target": self._redact_secrets(target)})
            else:
                await self.browser.click(_sanitize_selector(target))
                _record("click", {"target": self._redact_secrets(target)})
            return True

        if "type" in step_data:
            selector = self._substitute_vars(step_data.get("selector") or "")
            text = self._substitute_vars(step_data["type"])
            logger.info(f"  ⚡ Deterministic Type into {self._redact_secrets(selector)}")
            await self.browser.type_text(_sanitize_selector(selector), text)
            _record(
                "type_text",
                {"selector": self._redact_secrets(selector), "text": "[REDACTED]"},
            )
            return True

        if "frame_click" in step_data:
            fdata = step_data["frame_click"]
            frame = self._substitute_vars(fdata.get("frame") or "")
            target = self._substitute_vars(fdata.get("target") or "")
            logger.info(f"  ⚡ Deterministic Frame Click: frame={self._redact_secrets(frame)}, target={self._redact_secrets(target)}")
            await self.browser.frame_click(frame, _sanitize_selector(target))
            _record("frame_click", {"frame": self._redact_secrets(frame), "target": self._redact_secrets(target)})
            return True

        if "frame_type" in step_data:
            fdata = step_data["frame_type"]
            frame = self._substitute_vars(fdata.get("frame") or "")
            selector = self._substitute_vars(fdata.get("selector") or "")
            text = self._substitute_vars(fdata.get("text") or "")
            logger.info(f"  ⚡ Deterministic Frame Type: frame={self._redact_secrets(frame)}, selector={self._redact_secrets(selector)}")
            await self.browser.frame_type_text(frame, _sanitize_selector(selector), text)
            _record("frame_type_text", {"frame": self._redact_secrets(frame), "selector": self._redact_secrets(selector), "text": "[REDACTED]"})
            return True

        # 2) Action form
        action = step_data.get("action")
        if not action:
            return False
            
        action = str(action).strip()
        timeout_ms = int(step_data.get("timeout", self.action_timeout_ms))
        selector = step_data.get("selector")
        target = step_data.get("target")
        text = step_data.get("text")
        path = step_data.get("path")
        frame = step_data.get("frame")

        try:
            if action == "frame_wait_for_selector":
                f_sel = self._substitute_vars(frame or "")
                sel = self._substitute_vars(selector or target or "")
                logger.info(f"  ⚡ Deterministic Frame Wait: frame={self._redact_secrets(f_sel)} selector={self._redact_secrets(sel)}")
                await self.browser.frame_wait_for_selector(f_sel, _sanitize_selector(sel), timeout_ms=timeout_ms)
                _record("frame_wait_for_selector", {"frame": self._redact_secrets(f_sel), "selector": self._redact_secrets(sel)})
                return True

            if action in {"navigate", "goto"}:
                raw_nav = path or target or selector or "/"
                logger.info(f"  ⚡ Deterministic Navigate: {self._redact_secrets(raw_nav)}")
                nav = self._substitute_vars(raw_nav)
                await self.browser.navigate(nav)
                _record("navigate", {"path": self._redact_secrets(nav)})
                return True

            if action == "click":
                raw_click_target = target or selector or ""
                logger.info(f"  ⚡ Deterministic Click: {self._redact_secrets(raw_click_target)}")
                click_target = self._substitute_vars(raw_click_target)
                await self.browser.click(_sanitize_selector(click_target))
                _record("click", {"target": self._redact_secrets(click_target)})
                return True

            if action in {"type", "type_text", "fill"}:
                sel = self._substitute_vars(selector or "")
                val = self._substitute_vars(text or step_data.get("value") or "")
                logger.info(f"  ⚡ Deterministic Type into {self._redact_secrets(sel)}")
                await self.browser.type_text(_sanitize_selector(sel), val)
                _record("type_text", {"selector": self._redact_secrets(sel), "text": "[REDACTED]"})
                return True

            if action in {"wait_for_selector", "check_element", "assert_visible"}:
                sel = self._substitute_vars(selector or target or "")
                logger.info(f"  ⚡ Deterministic Wait: {self._redact_secrets(sel)}")
                await self.browser.wait_for_selector(_sanitize_selector(sel), timeout_ms=timeout_ms)
                _record(
                    "wait_for_selector",
                    {"selector": self._redact_secrets(sel), "timeout_ms": timeout_ms},
                )
                return True

            if action == "assert_text":
                sel = self._substitute_vars(selector or target or "body")
                required = self._substitute_vars(text or step_data.get("value") or "")
                logger.info(f"  ⚡ Deterministic Assert Text in {self._redact_secrets(sel)}: {self._redact_secrets(required)}")

                if sel == "body":
                    content = await self.browser.get_content()
                else:
                    content = await self.browser.get_text(_sanitize_selector(sel))

                if required not in content:
                    raise ValueError(f"Expected text not found in {sel}: {required}")
                _record(
                    "assert_text",
                    {"selector": self._redact_secrets(sel), "text": self._redact_secrets(required)},
                )
                return True

            # Unhandled action => let LLM handle it.
            return False
        except Exception:
            if optional:
                logger.info("  ⚠️ Optional deterministic step failed; continuing.")
                _record("optional_step_failed", {"action": action})
                return True
            raise

    async def run_story(
        self,
        story: AgentStory,
        glm_client: Any,
        output_dir: Path,
        deterministic_only: bool = False,
    ) -> StoryResult:
        """Run a full user story.
        
        Args:
            story: The story to execute
            glm_client: GLMVisionClient instance
            output_dir: Directory for artifacts
            deterministic_only: If true, skip non-deterministic steps
            
        Returns:
            StoryResult with status and evidence
        """
        logger.info(f"🚀 Running story: {story.id}")
        result = StoryResult(story_id=story.id, status="pass")
        
        for step_data in story.steps:
            step_id = step_data.get("id", "unknown")
            description = step_data.get("description", "")
            
            if deterministic_only and not step_data.get("deterministic", False):
                logger.info(f"  ⏭️ Skipping non-deterministic step: {step_id}")
                continue
                
            logger.info(f"  Step: {step_id} - {self._redact_secrets(description)}")
            
            start_time = time.time()
            step_res = await self._run_step(story.persona, step_id, step_data, deterministic_only=deterministic_only)
            step_res.duration_ms = int((time.time() - start_time) * 1000)
            
            result.step_results.append(step_res)
            
            if step_res.status != "pass":
                result.status = "fail"
                logger.error(f"  ❌ Step {step_id} failed. Halting story.")
                break
                
        return result

    async def _run_step(
        self, persona: str, step_id: str, step_data: dict[str, Any], deterministic_only: bool = False
    ) -> StepResult:
        """Run a single step of a story."""
        description = step_data.get("description", "")
        validation_criteria = step_data.get("validation_criteria", [])

        actions_taken = []
        errors = []

        # Variable substitution is allowed for deterministic steps only.
        # For LLM-driven steps we keep placeholders to avoid leaking secrets into logs/prompts.

        # llm-uismoke-qa-loop.2: Deterministic Step Execution
        if any(k in step_data for k in ["action", "click", "navigate", "type", "frame_click", "frame_type"]):
            logger.info(f"  ⚡ Attempting deterministic step: {step_id}")
            try:
                handled = await self._execute_deterministic_step(step_data, actions_taken)
                if handled:
                    # Final validation
                    current_url = await self.browser.get_current_url()
                    final_screenshot = await self.browser.screenshot()
                    verified = await self._verify_completion(final_screenshot, validation_criteria)
                    if verified:
                        return StepResult(
                            step_id=step_id,
                            status="pass",
                            actions_taken=actions_taken,
                            errors=errors,
                        )
                    errors.append(
                        AgentError(
                            type="verification_error",
                            severity="high",
                            message="Deterministic step verification failed",
                            url=current_url,
                        )
                    )
                    return StepResult(
                        step_id=step_id, status="fail", actions_taken=actions_taken, errors=errors
                    )
            except ValueError as e:
                logger.error(f"  ❌ Deterministic variable substitution failed: {e}")
                errors.append(AgentError(type="missing_env", severity="blocker", message=str(e)))
                return StepResult(
                    step_id=step_id, status="fail", actions_taken=actions_taken, errors=errors
                )
            except Exception as e:
                logger.error(f"  ❌ Deterministic execution failed: {e}")
                errors.append(AgentError(type="ui_error", severity="medium", message=str(e)))
                return StepResult(
                    step_id=step_id, status="fail", actions_taken=actions_taken, errors=errors
                )

            # Not handled deterministically => fall through to LLM loop.

        if deterministic_only:
            logger.warning(f"  ⏭️ Step {step_id} is not deterministic; skipping.")
            return StepResult(step_id=step_id, status="skip", actions_taken=actions_taken)

        for i in range(self.max_tool_iterations):
            # 1. Capture state
            current_url = await self.browser.get_current_url()
            screenshot_b64 = await self.browser.screenshot()

            # Check for infrastructure errors
            console = await self.browser.get_console_errors()
            for msg in console:
                logger.warning(f"  ⚠️ Browser Console: {msg}")
                errors.append(
                    AgentError(
                        type="console_error", severity="medium", message=msg, url=current_url
                    )
                )

            network = await self.browser.get_network_errors()
            for err in network:
                severity = "high" if str(err.get("status", "")).startswith("5") else "medium"
                errors.append(
                    AgentError(
                        type="network_error",
                        severity=severity,
                        message=f"{err.get('method')} {err.get('url')}: {err.get('message')}",
                        url=current_url,
                    )
                )

            # DEBUG: Save state before LLM call to diagnose Safety/Blank issues
            if self.evidence_dir:
                try:
                    import base64

                    timestamp = int(time.time())
                    debug_prefix = f"debug_{step_id}_{i}_{timestamp}"

                    # Save HTML
                    html_content = await self.browser.get_content()
                    with open(
                        self.evidence_dir / f"{debug_prefix}.html", "w", encoding="utf-8"
                    ) as f:
                        f.write(html_content)

                    # Save Screenshot
                    with open(self.evidence_dir / f"{debug_prefix}.png", "wb") as f:
                        f.write(base64.b64decode(screenshot_b64))

                    logger.info(f"  🔍 Debug evidence saved: {debug_prefix}")
                except Exception as e:
                    logger.warning(f"Failed to save debug evidence: {e}")

            # 2. Build prompt
            # For LLM steps, we do NOT substitute variables to avoid leaking secrets.
            # We keep the raw description which may contain {{ENV:...}}.
            # If the user put secrets in description without {{ENV:...}}, that's on them.
            # We explicitly redact any known {{ENV:...}} patterns if they are not meant for LLM.
            # But here, we just want to ensure we don't accidentally reveal the VALUE.
            
            prompt = (
                f"Step: {self._redact_secrets(description)}\nCurrent URL: {current_url}\n"
                "Goal: Complete the step described above."
            )

            validation_msg = ""
            if validation_criteria:
                validation_msg = (
                    "\n\nSTRICT VERIFICATION REQUIRED:\nThe screenshot MUST contain the following text fragments. If ANY are missing, the step is NOT complete and you MUST NOT call complete_step:\n"
                    + "\n".join([f'- "{t}"' for t in validation_criteria])
                )

            messages = [
                LLMMessage(
                    role=MessageRole.SYSTEM,
                    content=f"You are a QA Agent. Persona: {persona}. Your goal is to complete the user story step. Use the available tools to interact with the page.\n\nCRITICAL: If the screenshot is blank, black, or essential data is missing, YOU MUST NOT call complete_step.{validation_msg}\nInstead, try to wait or navigate again. If the page remains blank or verification fails after retries, fail the step by not calling complete_step and letting the loop finish.",
                ),
                LLMMessage(
                    role=MessageRole.USER,
                    content=[
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
                        },
                    ],
                ),
            ]

            # Define tools
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "navigate",
                        "description": "Navigate to a relative path",
                        "parameters": {
                            "type": "object",
                            "properties": {"path": {"type": "string"}},
                            "required": ["path"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "click",
                        "description": "Click an element by selector or text",
                        "parameters": {
                            "type": "object",
                            "properties": {"target": {"type": "string"}},
                            "required": ["target"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "type_text",
                        "description": "Type text into an input field",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "selector": {"type": "string"},
                                "text": {"type": "string"},
                            },
                            "required": ["selector", "text"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "wait",
                        "description": "Wait for a specified number of seconds (use if page is loading or blank)",
                        "parameters": {
                            "type": "object",
                            "properties": {"seconds": {"type": "integer"}},
                            "required": ["seconds"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "complete_step",
                        "description": "Call this when the step goal is achieved",
                        "parameters": {"type": "object", "properties": {}},
                    },
                },
            ]

            # 3. Call LLM (Vision model - try GLM-4.5v if 4.6v hits safety)
            # Note: We use raw_response from metadata to get tool calls if not mapped in core LLMResponse
            try:
                response = await self.llm.chat_completion(
                    messages=messages,
                    model="glm-4.6v",  # Explicit vision model
                    tools=tools,
                    tool_choice="auto",
                    extra_body={"thinking": {"type": "enabled"}},
                )
            except Exception as e:
                error_msg = str(e)
                if "safety" in error_msg.lower() or "1301" in error_msg or "1214" in error_msg:
                    logger.warning(
                        f"GLM-4.6v safety/error triggered, backoff 5s then trying GLM-4.5v: {e}"
                    )
                    await asyncio.sleep(5)
                    try:
                        response = await self.llm.chat_completion(
                            messages=messages,
                            model="glm-4.5v",  # Fallback vision model
                            tools=tools,
                            tool_choice="auto",
                            extra_body={"thinking": {"type": "enabled"}},
                        )
                    except Exception as e2:
                        logger.error(f"GLM-4.5v also failed, backoff 10s: {e2}")
                        await asyncio.sleep(10)
                        errors.append(
                            AgentError(
                                type="llm_error", severity="high", message=str(e2), url=current_url
                            )
                        )
                        continue
                else:
                    logger.error(f"LLM call failed: {e}")
                    errors.append(
                        AgentError(
                            type="llm_error", severity="high", message=error_msg, url=current_url
                        )
                    )
                    continue

            # 4. Handle Tool Calls
            # The current ZaiClient doesn't automatically map tool_calls to LLMResponse yet
            raw_response = response.metadata.get("raw_response", {})
            message = raw_response.get("choices", [{}])[0].get("message", {})
            tool_calls = message.get("tool_calls", [])

            if not tool_calls:
                # If no tool calls, but there is content, maybe it's just talking
                if response.content:
                    logger.info(f"  Agent: {response.content}")
                else:
                    logger.warning("Agent produced no tool calls or content. Retrying...")
                continue

            for tc in tool_calls:
                func = tc.get("function", {})
                name = func.get("name")
                args_str = func.get("arguments", "{}")
                try:
                    args = json.loads(args_str)
                except Exception:
                    args = {}

                # Redact text in actions_taken for tools that handle sensitive input
                log_args = dict(args)
                if name == "type_text" and "text" in log_args:
                    log_args["text"] = "[REDACTED]"
                actions_taken.append({"tool": name, "args": log_args})

                if name == "complete_step":
                    logger.info(
                        f"  ✅ Step {step_id} marked complete by agent. Running strict verification..."
                    )

                    final_screenshot = await self.browser.screenshot()

                    # P0 FIX (r7p): Strict Visual Verification
                    verified = await self._verify_completion(final_screenshot, validation_criteria)

                    # Capture final evidence if configured
                    if self.evidence_dir:
                        import base64

                        filename = f"{step_id}.png"
                        filepath = self.evidence_dir / filename
                        with open(filepath, "wb") as f:
                            f.write(base64.b64decode(final_screenshot))

                        # Save HTML content for debugging
                        try:
                            content = await self.browser.get_content()
                            html_path = self.evidence_dir / f"{step_id}.html"
                            with open(html_path, "w", encoding="utf-8") as f:
                                f.write(content)
                        except Exception as e:
                            logger.warning(f"Failed to save HTML source: {e}")

                        logger.info(f"  📸 Evidence saved: {filepath}")

                    if not verified:
                        logger.error(
                            f"  ❌ Verification failed for {step_id}. Continuing loop/failing."
                        )
                        errors.append(
                            AgentError(
                                type="verification_error",
                                severity="high",
                                message="Strict verification failed: required text not found in final screenshot",
                                url=current_url,
                            )
                        )
                        continue

                    return StepResult(
                        step_id=step_id, status="pass", actions_taken=actions_taken, errors=errors
                    )

                try:
                    if name == "navigate":
                        await self.browser.navigate(args.get("path", "/"))
                    elif name == "click":
                        target = args.get("target", "")
                        try:
                            target = _sanitize_selector(target)
                        except ValueError as ve:
                            logger.warning(f"Invalid click target, using raw: {ve}")
                        await self.browser.click(target)
                    elif name == "type_text":
                        raw_selector = args.get("selector", "")
                        text = args.get("text", "")

                        # Sanitize selector
                        try:
                            selector = _sanitize_selector(raw_selector)
                        except ValueError as ve:
                            logger.error(f"Cannot sanitize selector: {ve}")
                            errors.append(
                                AgentError(
                                    type="selector_error",
                                    severity="medium",
                                    message=f"Invalid selector: {ve}",
                                    url=current_url,
                                )
                            )
                            continue

                        # Get fallback selectors for input/textarea mismatch
                        selectors_to_try = _get_input_fallback_selectors(selector)

                        typed = False
                        last_error = None
                        for sel in selectors_to_try:
                            try:
                                await self.browser.type_text(sel, text)
                                if sel != selector:
                                    logger.info(f"  ✅ Fallback selector worked: {sel}")
                                typed = True
                                break
                            except Exception as e:
                                last_error = e
                                logger.debug(f"Selector {sel} failed: {e}")

                        if not typed:
                            raise last_error or Exception(
                                f"All selectors failed for: {raw_selector}"
                            )

                    elif name == "wait":
                        seconds = args.get("seconds", 2)
                        # Validate seconds is a number
                        if isinstance(seconds, str):
                            try:
                                seconds = int(float(seconds))
                            except ValueError:
                                seconds = 2
                        seconds = max(1, min(seconds, 30))  # Clamp to 1-30 seconds
                        logger.info(f"  ⏳ Waiting for {seconds} seconds...")
                        await asyncio.sleep(seconds)
                except Exception as e:
                    logger.error(f"  ❌ Tool error ({name}): {e}")
                    errors.append(
                        AgentError(
                            type="ui_error", severity="medium", message=str(e), url=current_url
                        )
                    )

        return StepResult(
            step_id=step_id, status="fail", actions_taken=actions_taken, errors=errors
        )

    async def _verify_completion(self, screenshot_b64: str, validation_criteria: list[str]) -> bool:
        """Strictly verify that required markers are present in the final screenshot (P0: affordabot-r7p)."""
        if not validation_criteria:
            return True

        prompt = "EXACT TEXT EXTRACTION TASK:\nExtract all visible text, numbers, and labels from this UI screenshot. Provide a clean list of text fragments you see. If the image is blank or black, say 'EMPTY'."

        try:
            response = await self.llm.chat_completion(
                messages=[
                    LLMMessage(
                        role=MessageRole.SYSTEM,
                        content="You are a precise OCR agent. Extract all text exactly as shown. No conversational filler.",
                    ),
                    LLMMessage(
                        role=MessageRole.USER,
                        content=[
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
                            },
                        ],
                    ),
                ],
                model="glm-4.5v",  # Use 4.5v for extraction
                temperature=0.0,
            )

            extracted_text = response.content.lower()
            if "empty" in extracted_text and len(extracted_text) < 20:
                logger.warning("  ❌ Verification failed: Screenshot is reported as EMPTY.")
                return False

            missing = []
            for criterion in validation_criteria:
                # Basic fuzzy check (lowercase, stripped)
                if criterion.lower().strip() not in extracted_text:
                    missing.append(criterion)

            if missing:
                logger.warning(f"  ❌ VERIFICATION FAILED. Missing markers: {missing}")
                return False

            logger.info("  ✅ VERIFICATION PASSED. All criteria found in screenshot.")
            return True
        except Exception as e:
            logger.error(f"Verification call failed: {e}")
            return False  # Fail safe on error
