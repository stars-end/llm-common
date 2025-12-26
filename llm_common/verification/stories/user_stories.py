"""
User Stories for Prime-Radiant verification.

These stories cover all user-facing functionality with visual validation.
Import these into prime-radiant's unified_verify.py.
"""

from ..framework import VerificationStory, StoryCategory


def get_user_stories() -> list[VerificationStory]:
    """
    Return all Prime-Radiant user story verifications.
    
    Stories cover:
    - Health check
    - Authentication
    - Deep Chat SSE
    - Accounts, Securities, Analytics
    - System info and Metrics
    """
    return [
        VerificationStory(
            id="pr_01_health",
            name="Health Check",
            category=StoryCategory.USER_STORY,
            phase=1,
            requires_browser=False,
            requires_llm=False,
            description="Verify /health endpoint returns 200 OK",
        ),
        VerificationStory(
            id="pr_02_auth",
            name="Auth & Profile",
            category=StoryCategory.USER_STORY,
            phase=2,
            requires_browser=True,
            requires_llm=True,
            llm_model="glm-4.6v",
            screenshot_selector="body",
            glm_prompt="Analyze this login/profile page. Describe the authentication UI elements visible.",
            description="Login and view user profile",
        ),
        VerificationStory(
            id="pr_03_chat",
            name="Deep Chat SSE",
            category=StoryCategory.USER_STORY,
            phase=3,
            requires_browser=True,
            requires_llm=True,
            llm_model="glm-4.6",  # For generating chat, not vision
            screenshot_selector="body",
            glm_prompt="Analyze this chat interface. Describe the message history, input area, and any streaming indicators.",
            description="Test SSE streaming chat with real LLM response",
        ),
        VerificationStory(
            id="pr_04_accounts",
            name="Accounts List",
            category=StoryCategory.USER_STORY,
            phase=4,
            requires_browser=True,
            requires_llm=True,
            llm_model="glm-4.6v",
            screenshot_selector="body",
            glm_prompt="Analyze this accounts list page. Describe the table columns and any visible account data.",
            description="View list of financial accounts",
        ),
        VerificationStory(
            id="pr_05_securities",
            name="Securities Search",
            category=StoryCategory.USER_STORY,
            phase=5,
            requires_browser=True,
            requires_llm=True,
            llm_model="glm-4.6v",
            screenshot_selector="body",
            glm_prompt="Analyze this securities search page. Describe the search input, filters, and results displayed.",
            description="Search for securities by symbol",
        ),
        VerificationStory(
            id="pr_06_analytics",
            name="Analytics Summary",
            category=StoryCategory.USER_STORY,
            phase=6,
            requires_browser=True,
            requires_llm=True,
            llm_model="glm-4.6v",
            screenshot_selector="body",
            glm_prompt="Analyze this analytics dashboard. Describe the charts, metrics, and data visualizations.",
            description="View portfolio analytics summary",
        ),
        VerificationStory(
            id="pr_07_system",
            name="System Info",
            category=StoryCategory.USER_STORY,
            phase=7,
            requires_browser=False,
            requires_llm=False,
            description="Verify system info endpoint returns valid data",
        ),
        VerificationStory(
            id="pr_08_metrics",
            name="Metrics List",
            category=StoryCategory.USER_STORY,
            phase=8,
            requires_browser=False,
            requires_llm=False,
            description="Verify metrics endpoint returns monitoring data",
        ),
    ]
