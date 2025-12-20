import json
import logging
import time
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Union

from llm_common.core import LLMClient, LLMMessage, MessageRole
from llm_common.agents.schemas import (
    AgentStory, 
    StepResult, 
    StoryResult, 
    AgentError
)

logger = logging.getLogger(__name__)

class BrowserAdapter(Protocol):
    """Protocol for browser interaction."""
    async def navigate(self, path: str) -> None: ...
    async def click(self, target: str) -> None: ...
    async def type_text(self, selector: str, text: str) -> None: ...
    async def screenshot(self) -> str: ...  # Base64 string
    async def get_console_errors(self) -> List[str]: ...
    async def get_network_errors(self) -> List[Dict[str, Any]]: ...
    async def wait_for_selector(self, selector: str, timeout_ms: int = 5000) -> None: ...
    async def get_current_url(self) -> str: ...
    async def close(self) -> None: ...

class UISmokeAgent:
    """Agent that executes UI smoke tests using vision + tool calling."""
    
    def __init__(
        self,
        glm_client: LLMClient,
        browser: BrowserAdapter,
        base_url: str,
        max_tool_iterations: int = 10,
        evidence_dir: Optional[str] = None
    ):
        """Initialize UI Smoke Agent.
        
        Args:
            glm_client: LLM client (must support vision)
            browser: Adapter for browser interactions
            base_url: Base URL for relative navigation
            max_tool_iterations: Max actions per step
            evidence_dir: Directory to save step-completion screenshots
        """
        self.llm = glm_client
        self.browser = browser
        self.base_url = base_url
        self.max_tool_iterations = max_tool_iterations
        self.evidence_dir = Path(evidence_dir) if evidence_dir else None
        
        if self.evidence_dir:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)

    async def run_story(self, story: AgentStory) -> StoryResult:
        """Run a full user story.
        
        Args:
            story: The story to execute
            
        Returns:
            StoryResult with status and errors
        """
        logger.info(f"🚀 Running story: {story.id}")
        story_errors = []
        step_results = []
        
        for step_data in story.steps:
            step_id = step_data.get("id", "unknown")
            description = step_data.get("description", "")
            validation_criteria = step_data.get("validation_criteria", [])
            logger.info(f"  Step: {step_id} - {description}")
            
            start_time = time.time()
            step_result = await self._run_step(story.persona, step_id, description, validation_criteria)
            step_result.duration_ms = int((time.time() - start_time) * 1000)
            
            step_results.append(step_result)
            story_errors.extend(step_result.errors)
            
            if step_result.status == "fail":
                logger.error(f"  ❌ Step {step_id} failed. Halting story.")
                break
                
        status = "pass" if all(r.status == "pass" for r in step_results) else "fail"
        return StoryResult(
            story_id=story.id,
            status=status,
            step_results=step_results,
            errors=story_errors
        )

    async def _run_step(self, persona: str, step_id: str, description: str, validation_criteria: List[str] = None) -> StepResult:
        """Run a single step of a story."""
        actions_taken = []
        errors = []
        
        for i in range(self.max_tool_iterations):
            # 1. Capture state
            current_url = await self.browser.get_current_url()
            screenshot_b64 = await self.browser.screenshot()
            
            # Check for infrastructure errors
            console = await self.browser.get_console_errors()
            for msg in console:
                logger.warning(f"  ⚠️ Browser Console: {msg}")
                errors.append(AgentError(type="console_error", severity="medium", message=msg, url=current_url))
                
            network = await self.browser.get_network_errors()
            for err in network:
                severity = "high" if str(err.get("status", "")).startswith("5") else "medium"
                errors.append(AgentError(type="network_error", severity=severity, message=f"{err.get('method')} {err.get('url')}: {err.get('message')}", url=current_url))

            # DEBUG: Save state before LLM call to diagnose Safety/Blank issues
            if self.evidence_dir:
                try:
                    import base64
                    timestamp = int(time.time())
                    debug_prefix = f"debug_{step_id}_{i}_{timestamp}"
                    
                    # Save HTML
                    html_content = await self.browser.get_content()
                    with open(self.evidence_dir / f"{debug_prefix}.html", "w", encoding="utf-8") as f:
                        f.write(html_content)
                    
                    # Save Screenshot
                    with open(self.evidence_dir / f"{debug_prefix}.png", "wb") as f:
                        f.write(base64.b64decode(screenshot_b64))
                        
                    logger.info(f"  🔍 Debug evidence saved: {debug_prefix}")
                except Exception as e:
                    logger.warning(f"Failed to save debug evidence: {e}")

            # 2. Build prompt
            prompt = f"Step: {description}\nCurrent URL: {current_url}\nGoal: Complete the step described above."
            
            validation_msg = ""
            if validation_criteria:
                validation_msg = "\n\nSTRICT VERIFICATION REQUIRED:\nThe screenshot MUST contain the following text fragments. If ANY are missing, the step is NOT complete and you MUST NOT call complete_step:\n" + "\n".join([f"- \"{t}\"" for t in validation_criteria])

            messages = [
                LLMMessage(
                    role=MessageRole.SYSTEM, 
                    content=f"You are a QA Agent. Persona: {persona}. Your goal is to complete the user story step. Use the available tools to interact with the page.\n\nCRITICAL: If the screenshot is blank, black, or essential data is missing, YOU MUST NOT call complete_step.{validation_msg}\nInstead, try to wait or navigate again. If the page remains blank or verification fails after retries, fail the step by not calling complete_step and letting the loop finish."
                ),
                LLMMessage(
                    role=MessageRole.USER,
                    content=[
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
                    ]
                )
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
                            "required": ["path"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "click",
                        "description": "Click an element by selector or text",
                        "parameters": {
                            "type": "object",
                            "properties": {"target": {"type": "string"}},
                            "required": ["target"]
                        }
                    }
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
                                "text": {"type": "string"}
                            },
                            "required": ["selector", "text"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "wait",
                        "description": "Wait for a specified number of seconds (use if page is loading or blank)",
                        "parameters": {
                            "type": "object",
                            "properties": {"seconds": {"type": "integer"}},
                            "required": ["seconds"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "complete_step",
                        "description": "Call this when the step goal is achieved",
                        "parameters": {"type": "object", "properties": {}}
                    }
                }
            ]
            
            # 3. Call LLM (Vision model - try GLM-4.5v if 4.6v hits safety)
            # Note: We use raw_response from metadata to get tool calls if not mapped in core LLMResponse
            try:
                response = await self.llm.chat_completion(
                    messages=messages,
                    model="glm-4.6v",  # Explicit vision model
                    tools=tools,
                    tool_choice="auto",
                    extra_body={"thinking": {"type": "enabled"}}
                )
            except Exception as e:
                error_msg = str(e)
                if "safety" in error_msg.lower() or "1301" in error_msg or "1214" in error_msg:
                    logger.warning(f"GLM-4.6v safety/error triggered, backoff 5s then trying GLM-4.5v: {e}")
                    await asyncio.sleep(5)
                    try:
                        response = await self.llm.chat_completion(
                            messages=messages,
                            model="glm-4.5v",  # Fallback vision model
                            tools=tools,
                            tool_choice="auto",
                            extra_body={"thinking": {"type": "enabled"}}
                        )
                    except Exception as e2:
                        logger.error(f"GLM-4.5v also failed, backoff 10s: {e2}")
                        await asyncio.sleep(10)
                        errors.append(AgentError(type="llm_error", severity="high", message=str(e2), url=current_url))
                        continue
                else:
                    logger.error(f"LLM call failed: {e}")
                    errors.append(AgentError(type="llm_error", severity="high", message=error_msg, url=current_url))
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
                except:
                    args = {}
                
                actions_taken.append({"tool": name, "args": args})
                
                if name == "complete_step":
                    logger.info(f"  ✅ Step {step_id} marked complete by agent. Running strict verification...")
                    
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
                        logger.error(f"  ❌ Verification failed for {step_id}. Continuing loop/failing.")
                        errors.append(AgentError(type="verification_error", severity="high", message="Strict verification failed: required text not found in final screenshot", url=current_url))
                        continue
                        
                    return StepResult(step_id=step_id, status="pass", actions_taken=actions_taken, errors=errors)
                
                try:
                    if name == "navigate":
                        await self.browser.navigate(args.get("path", "/"))
                    elif name == "click":
                        await self.browser.click(args.get("target", ""))
                    elif name == "type_text":
                        await self.browser.type_text(args.get("selector", ""), args.get("text", ""))
                    elif name == "wait":
                        seconds = args.get("seconds", 2)
                        logger.info(f"  ⏳ Waiting for {seconds} seconds...")
                        await asyncio.sleep(seconds)
                except Exception as e:
                    logger.error(f"  ❌ Tool error ({name}): {e}")
                    errors.append(AgentError(type="ui_error", severity="medium", message=str(e), url=current_url))

        return StepResult(step_id=step_id, status="fail", actions_taken=actions_taken, errors=errors)

    async def _verify_completion(self, screenshot_b64: str, validation_criteria: List[str]) -> bool:
        """Strictly verify that required markers are present in the final screenshot (P0: affordabot-r7p)."""
        if not validation_criteria:
            return True
            
        prompt = "EXACT TEXT EXTRACTION TASK:\nExtract all visible text, numbers, and labels from this UI screenshot. Provide a clean list of text fragments you see. If the image is blank or black, say 'EMPTY'."
        
        try:
            response = await self.llm.chat_completion(
                messages=[
                    LLMMessage(role=MessageRole.SYSTEM, content="You are a precise OCR agent. Extract all text exactly as shown. No conversational filler."),
                    LLMMessage(role=MessageRole.USER, content=[
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}}
                    ])
                ],
                model="glm-4.5v", # Use 4.5v for extraction
                temperature=0.0
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
            return False # Fail safe on error
