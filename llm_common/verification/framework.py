"""
Unified Verification Framework for GLM-4.6V powered E2E testing.

This module provides the core classes for running verification stories
across affordabot (RAG pipeline) and prime-radiant (user stories) with
consistent screenshot capture and report generation.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, List
from datetime import datetime
from pathlib import Path
from enum import Enum
import asyncio
import logging
import os

logger = logging.getLogger("verification.framework")


class StoryCategory(str, Enum):
    """Category of verification story."""
    RAG_PIPELINE = "rag"       # Affordabot RAG pipeline
    USER_STORY = "pr"          # Prime-radiant user story
    INTEGRATION = "int"        # Cross-service integration


class StoryStatus(str, Enum):
    """Status of a verification story."""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class VerificationStory:
    """
    Definition of a single verification story.
    
    A story represents one testable unit - e.g., "RAG Discovery" or "Deep Chat".
    """
    id: str                                    # e.g., "rag_01_discovery"
    name: str                                  # e.g., "Discovery: LLM Query Generation"
    category: StoryCategory
    phase: int                                 # 0-11 for ordering
    run: Optional[Callable] = None             # async function to execute
    screenshot_selector: Optional[str] = None  # CSS selector for screenshot
    glm_prompt: str = "Describe the main UI elements visible in this screenshot."
    requires_browser: bool = False             # Does this need Playwright?
    requires_llm: bool = False                 # Does this use LLM calls?
    llm_model: str = "glm-4.6"                # Which model to use
    timeout_seconds: int = 60
    description: str = ""
    
    @property
    def screenshot_name(self) -> str:
        """Standardized screenshot filename."""
        return f"{self.category.value}_{self.phase:02d}_{self.id.split('_')[-1]}.png"


@dataclass
class StoryResult:
    """Result of executing a verification story."""
    story: VerificationStory
    status: StoryStatus
    screenshot_path: Optional[str] = None
    glm_response: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    llm_calls: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def passed(self) -> bool:
        return self.status == StoryStatus.PASSED


@dataclass
class VerificationConfig:
    """Configuration for the verification run."""
    run_id: str = field(default_factory=lambda: f"verify-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    artifacts_dir: str = "artifacts/verification"
    enable_screenshots: bool = True
    enable_glm_validation: bool = True
    glm_api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout_seconds: int = 300
    parallel: bool = False  # Run stories in parallel?
    
    @property
    def run_dir(self) -> Path:
        """Directory for this verification run."""
        return Path(self.artifacts_dir) / self.run_id
    
    @property
    def screenshots_dir(self) -> Path:
        """Directory for screenshots."""
        return self.run_dir / "screenshots"
    
    @property
    def logs_dir(self) -> Path:
        """Directory for logs."""
        return self.run_dir / "logs"


@dataclass
class VerificationReport:
    """Complete verification report."""
    config: VerificationConfig
    results: List[StoryResult] = field(default_factory=list)
    start_time: str = ""
    end_time: str = ""
    
    @property
    def total(self) -> int:
        return len(self.results)
    
    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == StoryStatus.PASSED)
    
    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == StoryStatus.FAILED)
    
    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == StoryStatus.SKIPPED)
    
    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100
    
    @property
    def total_llm_calls(self) -> int:
        return sum(r.llm_calls for r in self.results)
    
    def by_category(self, category: StoryCategory) -> List[StoryResult]:
        """Get results for a specific category."""
        return [r for r in self.results if r.story.category == category]


class UnifiedVerifier:
    """
    Main verification orchestrator.
    
    Runs verification stories with GLM-4.6V visual validation,
    captures screenshots, and generates reports.
    
    Usage:
        verifier = UnifiedVerifier(config)
        verifier.register_story(story)
        report = await verifier.run_all()
    """
    
    def __init__(self, config: VerificationConfig):
        self.config = config
        self.stories: List[VerificationStory] = []
        self.browser = None
        self.page = None
        self.glm_client = None
        
    def register_story(self, story: VerificationStory) -> None:
        """Register a story for verification."""
        self.stories.append(story)
        self.stories.sort(key=lambda s: (s.category.value, s.phase))
        
    def register_stories(self, stories: List[VerificationStory]) -> None:
        """Register multiple stories."""
        for story in stories:
            self.register_story(story)
    
    async def _setup(self) -> None:
        """Setup verification environment."""
        # Create directories
        self.config.run_dir.mkdir(parents=True, exist_ok=True)
        self.config.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.config.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup GLM client if validation enabled
        if self.config.enable_glm_validation:
            api_key = self.config.glm_api_key or os.environ.get("ZAI_API_KEY")
            if api_key:
                try:
                    from llm_common.core import LLMConfig
                    from llm_common.providers import ZaiClient
                    self.glm_client = ZaiClient(LLMConfig(
                        api_key=api_key,
                        provider="zai",
                        default_model="glm-4.6"
                    ))
                    logger.info("GLM client initialized for visual validation")
                except Exception as e:
                    logger.warning(f"Failed to initialize GLM client: {e}")
        
        # Setup browser if any story requires it
        if any(s.requires_browser for s in self.stories):
            try:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                self.browser = await self._playwright.chromium.launch(headless=True)
                self.page = await self.browser.new_page(viewport={"width": 1280, "height": 800})
                logger.info("Browser initialized for visual testing")
            except Exception as e:
                logger.warning(f"Failed to initialize browser: {e}")
    
    async def _teardown(self) -> None:
        """Cleanup verification environment."""
        if self.browser:
            await self.browser.close()
        if hasattr(self, '_playwright'):
            await self._playwright.stop()
    
    async def _run_story(self, story: VerificationStory) -> StoryResult:
        """Execute a single verification story."""
        start_time = datetime.now()
        result = StoryResult(story=story, status=StoryStatus.RUNNING)
        
        try:
            logger.info(f"▶️ Running: {story.id} - {story.name}")
            
            # Execute the story function if provided
            if story.run:
                await asyncio.wait_for(
                    story.run(self),
                    timeout=story.timeout_seconds
                )
            
            # Capture screenshot if browser available and selector provided
            if self.page and story.screenshot_selector:
                screenshot_path = self.config.screenshots_dir / story.screenshot_name
                await self.page.screenshot(path=str(screenshot_path))
                result.screenshot_path = str(screenshot_path)
                logger.info(f"📸 Screenshot: {screenshot_path}")
            
            # GLM visual validation if enabled
            if self.glm_client and story.requires_llm and result.screenshot_path:
                result.glm_response = await self._validate_with_glm(
                    result.screenshot_path, 
                    story.glm_prompt
                )
                result.llm_calls += 1
            
            result.status = StoryStatus.PASSED
            logger.info(f"✅ Passed: {story.id}")
            
        except asyncio.TimeoutError:
            result.status = StoryStatus.FAILED
            result.error = f"Timeout after {story.timeout_seconds}s"
            logger.error(f"❌ Timeout: {story.id}")
            
        except Exception as e:
            result.status = StoryStatus.FAILED
            result.error = str(e)
            logger.error(f"❌ Failed: {story.id} - {e}")
        
        result.duration_seconds = (datetime.now() - start_time).total_seconds()
        return result
    
    async def _validate_with_glm(self, screenshot_path: str, prompt: str) -> str:
        """Validate screenshot using GLM-4.6V."""
        try:
            import base64
            from llm_common.core.models import LLMMessage, MessageRole
            
            # Read and encode image
            with open(screenshot_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
            
            # Create vision message
            message = LLMMessage(
                role=MessageRole.USER,
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}
                ]
            )
            
            response = await self.glm_client.chat_completion(
                messages=[message],
                model="glm-4.6v"
            )
            
            return response.content
            
        except Exception as e:
            logger.warning(f"GLM validation failed: {e}")
            return f"GLM validation error: {e}"
    
    async def run_all(self) -> VerificationReport:
        """Run all registered verification stories."""
        report = VerificationReport(
            config=self.config,
            start_time=datetime.now().isoformat()
        )
        
        try:
            await self._setup()
            
            for story in self.stories:
                result = await self._run_story(story)
                report.results.append(result)
            
        finally:
            await self._teardown()
            report.end_time = datetime.now().isoformat()
        
        return report
    
    async def run_category(self, category: StoryCategory) -> VerificationReport:
        """Run only stories in a specific category."""
        filtered = [s for s in self.stories if s.category == category]
        original_stories = self.stories
        self.stories = filtered
        
        try:
            return await self.run_all()
        finally:
            self.stories = original_stories
