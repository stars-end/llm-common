"""UI Smoke Agent - Core agent that drives browser via GLM-4.6V vision.

This agent:
1. Takes screenshots of the current page
2. Sends them to GLM-4.6V with step instructions
3. Executes tool calls (navigate, click, type)
4. Collects errors and produces results
"""

import json
import logging
import time
from typing import TYPE_CHECKING, Protocol

from .exceptions import ElementNotFoundError, NavigationError
from .glm_client import BROWSER_TOOLS, GLMVisionClient
from .models import AgentErrorData as AgentError, StepResult, Story, StoryResult, StoryStep

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class BrowserAdapter(Protocol):
    """Protocol for browser adapters.
    
    Implementations must provide async methods for browser control.
    See prime-radiant-ai/scripts/e2e_agent/browser_adapter.py for reference.
    """
    
    async def navigate(self, path: str) -> None:
        """Navigate to a URL path."""
        ...
    
    async def click(self, target: str) -> None:
        """Click an element by selector or text."""
        ...
    
    async def type_text(self, selector: str, text: str) -> None:
        """Type text into an input field."""
        ...
    
    async def wait_for_selector(self, selector: str, timeout: int = 5000) -> None:
        """Wait for an element to appear."""
        ...
    
    async def screenshot(self) -> str:
        """Take a screenshot and return base64-encoded PNG."""
        ...
    
    async def get_current_url(self) -> str:
        """Get the current page URL."""
        ...
    
    async def get_console_errors(self) -> list[str]:
        """Get console errors from the page."""
        ...
    
    async def get_network_errors(self) -> list[dict]:
        """Get network errors (4xx, 5xx responses)."""
        ...


SYSTEM_PROMPT = """You are a QA automation agent testing a web application.

Your role:
- Follow the step instructions carefully
- Use tools to interact with the browser (navigate, click, type_text)
- Report any errors or issues you observe
- Call complete_step when the step objective is achieved

Current persona: {persona}

Guidelines:
- Look at the screenshot carefully to find UI elements
- Use CSS selectors or text= patterns for clicking
- If you can't find an element, try alternative approaches
- Report errors immediately when found
- Be methodical and thorough
"""


class UISmokeAgent:
    """Agent that executes user stories using GLM-4.6V vision."""

    def __init__(
        self,
        glm_client: GLMVisionClient,
        browser: BrowserAdapter,
        base_url: str,
        max_tool_iterations: int = 10,
    ):
        """Initialize the agent.

        Args:
            glm_client: GLM vision client
            browser: Browser adapter implementing BrowserAdapter protocol
            base_url: Base URL of the application
            max_tool_iterations: Max iterations per step
        """
        self.glm_client = glm_client
        self.browser = browser
        self.base_url = base_url
        self.max_iterations = max_tool_iterations

    async def run_story(self, story: Story) -> StoryResult:
        """Execute a complete user story.

        Args:
            story: Story specification

        Returns:
            StoryResult with all step results and errors
        """
        logger.info(f"Running story: {story.id}")
        step_results = []
        all_errors = []

        for step in story.steps:
            try:
                result = await self._run_step(step, story.persona)
                step_results.append(result)
                all_errors.extend(result.errors)

                if result.status == "fail":
                    # Check if any blocker errors
                    blockers = [e for e in result.errors if e.severity == "blocker"]
                    if blockers:
                        logger.error(f"Blocker error in step {step.id}, stopping story")
                        break

            except Exception as e:
                logger.exception(f"Unexpected error in step {step.id}")
                error = AgentError(
                    type="unknown",
                    severity="blocker",
                    message=f"Step execution failed: {e}",
                )
                step_results.append(StepResult(
                    step_id=step.id,
                    status="fail",
                    errors=[error],
                ))
                all_errors.append(error)
                break

        # Determine overall status
        failed_steps = [r for r in step_results if r.status == "fail"]
        status = "fail" if failed_steps else "pass"

        return StoryResult(
            story_id=story.id,
            status=status,
            step_results=step_results,
            errors=all_errors,
        )

    async def _run_step(self, step: StoryStep, persona: str) -> StepResult:
        """Execute a single story step.

        Args:
            step: Step specification
            persona: User persona for context

        Returns:
            StepResult with actions and errors
        """
        logger.info(f"Running step: {step.id}")
        start_time = time.time()

        actions_taken = []
        errors = []
        step_complete = False
        iteration = 0

        while not step_complete and iteration < self.max_iterations:
            iteration += 1
            logger.debug(f"Step {step.id} iteration {iteration}")

            # Capture screenshot
            screenshot = await self.browser.screenshot()
            current_url = await self.browser.get_current_url()

            # Check for console/network errors
            console_errors = await self.browser.get_console_errors()
            for err in console_errors:
                errors.append(AgentError(
                    type="console_error",
                    severity="medium",
                    message=err,
                    url=current_url,
                ))

            network_errors = await self.browser.get_network_errors()
            for err in network_errors:
                severity = "high" if err.get("status", 0) >= 500 else "medium"
                errors.append(AgentError(
                    type="api_5xx" if severity == "high" else "api_4xx",
                    severity=severity,
                    message=f"{err.get('method')} {err.get('url')} -> {err.get('status')}",
                    url=current_url,
                    details=err,
                ))

            # Build prompt
            prompt = f"""Step: {step.id}
Objective: {step.description}

Current URL: {current_url}
Exploration budget remaining: {step.exploration_budget}

Look at the screenshot and decide what action to take.
Call complete_step when the objective is achieved.
"""

            # Call GLM
            try:
                response = await self.glm_client.chat_with_vision(
                    text=prompt,
                    image_base64=screenshot,
                    system_prompt=SYSTEM_PROMPT.format(persona=persona),
                    tools=BROWSER_TOOLS,
                    tool_choice="auto",
                )
            except Exception as e:
                logger.error(f"GLM API error: {e}")
                errors.append(AgentError(
                    type="api_error",
                    severity="blocker",
                    message=f"GLM API failed: {e}",
                ))
                break

            # Process response
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    func = tool_call.get("function", {})
                    tool_name = func.get("name")
                    tool_args = json.loads(func.get("arguments", "{}"))

                    actions_taken.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "iteration": iteration,
                    })

                    # Execute tool
                    result, should_complete, new_errors = await self._execute_tool(
                        tool_name, tool_args
                    )
                    errors.extend(new_errors)

                    if should_complete:
                        step_complete = True
                        break

            elif response.content:
                # No tool calls, just content - log it
                logger.info(f"GLM response: {response.content[:200]}...")

            # Check finish reason
            if response.finish_reason == "stop" and not response.tool_calls:
                # Model stopped without completing - may be stuck
                logger.warning("GLM stopped without tool calls or completion")
                if iteration >= 3:
                    errors.append(AgentError(
                        type="ui_error",
                        severity="high",
                        message="Agent stuck - could not complete step",
                    ))
                    break

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Determine status
        blocker_errors = [e for e in errors if e.severity == "blocker"]
        high_errors = [e for e in errors if e.severity == "high"]

        if blocker_errors:
            status = "fail"
        elif step_complete:
            status = "pass"
        elif high_errors:
            status = "fail"
        else:
            status = "pass"  # Completed max iterations without blockers

        return StepResult(
            step_id=step.id,
            status=status,
            actions_taken=actions_taken,
            errors=errors,
            duration_ms=duration_ms,
        )

    async def _execute_tool(
        self, tool_name: str, args: dict
    ) -> tuple[str, bool, list[AgentError]]:
        """Execute a browser tool.

        Args:
            tool_name: Name of the tool
            args: Tool arguments

        Returns:
            Tuple of (result_message, should_complete_step, errors)
        """
        errors = []
        should_complete = False

        try:
            if tool_name == "navigate":
                path = args.get("path", "/")
                await self.browser.navigate(path)
                return f"Navigated to {path}", False, errors

            elif tool_name == "click":
                target = args.get("target", "")
                await self.browser.click(target)
                return f"Clicked {target}", False, errors

            elif tool_name == "type_text":
                selector = args.get("selector", "")
                text = args.get("text", "")
                await self.browser.type_text(selector, text)
                return f"Typed into {selector}", False, errors

            elif tool_name == "wait_for_element":
                selector = args.get("selector", "")
                timeout = args.get("timeout_ms", 5000)
                await self.browser.wait_for_selector(selector, timeout)
                return f"Element {selector} appeared", False, errors

            elif tool_name == "complete_step":
                notes = args.get("notes", "")
                logger.info(f"Step completed: {notes}")
                return "Step completed", True, errors

            elif tool_name == "report_error":
                error = AgentError(
                    type=args.get("type", "other"),
                    severity=args.get("severity", "medium"),
                    message=args.get("message", "Unknown error"),
                )
                errors.append(error)
                return f"Reported error: {error.message}", False, errors

            else:
                logger.warning(f"Unknown tool: {tool_name}")
                return f"Unknown tool: {tool_name}", False, errors

        except NavigationError as e:
            error = AgentError(
                type="navigation_error",
                severity="blocker",
                message=str(e),
            )
            errors.append(error)
            return f"Navigation failed: {e}", False, errors

        except ElementNotFoundError as e:
            error = AgentError(
                type="ui_error",
                severity="high",
                message=str(e),
            )
            errors.append(error)
            return f"Element not found: {e}", False, errors

        except Exception as e:
            error = AgentError(
                type="unknown",
                severity="high",
                message=f"Tool execution failed: {e}",
            )
            errors.append(error)
            return f"Tool failed: {e}", False, errors
