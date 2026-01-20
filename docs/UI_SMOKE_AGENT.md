# UI Smoke Agent

Vision-powered UI testing system using GLM-4.6V for browser automation.

## Overview

The UI Smoke Agent combines:
- **GLM-4.6V**: Vision + tool calling for intelligent browser interaction
- **Playwright**: Real browser automation
- **Structured stories**: YAML user journey specifications
- **Error reporting**: Console, network, UI error detection → Beads issues

This is designed for **milestone-triggered smoke tests**, not per-PR testing. Use it to validate critical user journeys against dev/staging/prod environments.

## Architecture

```
Persona Schema (YAML) ──┐
                         ├─→ Story Specs (YAML) → UISmokeAgent → GLM-4.6V + BrowserAdapter
                         │                                ↓
Bootstrap (env vars) ────┘                       StoryResult / SmokeRunReport
                                                          ↓
                                                  Reporter Script
                                                          ↓
                                                    Beads Issues
```

### Component Flow

1. **Persona Schema** (`Persona` models): Defines test users WITHOUT secrets, references env var names
2. **Bootstrap Script** (repo-specific): Loads secrets from environment, resolves persona credentials
3. **Story Specs** (YAML): User journeys with persona reference, steps, exploration budgets
4. **UISmokeAgent**: Orchestrates execution, sends screenshots + prompts to GLM, executes tool calls
5. **GLM-4.6V Client**: Vision + tool calling, decides browser actions based on screenshots
6. **BrowserAdapter** (protocol): Playwright/Selenium implementation, executes browser actions
7. **StoryResult / SmokeRunReport**: Structured errors, actions, metadata
8. **Reporter Script** (repo-specific): Converts errors to Beads issues via `bd create`

### Separation of Concerns

- **llm-common**: Core abstractions (UISmokeAgent, BrowserAdapter, Persona schema, prompts)
- **Application repos**: Story specs, browser adapter implementation, bootstrap, reporter, workflows

## Quick Start

### 1. Install Dependencies

```bash
# In your repo (e.g., prime-radiant-ai, affordabot)
cd packages/llm-common
pip install poetry
poetry install -E agents  # Installs PyYAML

# Install Playwright
pip install playwright
playwright install chromium
```

### 2. Create Story Specs

Create `docs/TESTING/STORIES/my-story.yml`:

```yaml
id: story-login-dashboard
persona: "New user exploring the application"

steps:
  # Steps can be either structured dicts (recommended) or simple strings.
  # Simple strings are normalized into {id, description, validation_criteria: []}.
  - id: step-1-login
    description: |
      Navigate to /login and authenticate using test credentials.
      Verify successful redirect to dashboard.
    exploration_budget: 0

  - id: step-2-dashboard
    description: |
      Verify dashboard loads with user data.
      Check for errors or blank states.
    exploration_budget: 2

metadata:
  tags: ["core-flow"]
  priority: 1
```

### 3. Implement Browser Adapter

Create `scripts/e2e_agent/browser_adapter.py`:

```python
from llm_common.agents import BrowserAdapter
from playwright.async_api import Page

class MyPlaywrightAdapter:
    """Playwright implementation of BrowserAdapter."""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url.rstrip("/")
        self._console_errors = []
        self._network_errors = []
        self._setup_listeners()

    def _setup_listeners(self):
        def on_console(msg):
            if msg.type in ("error", "warning"):
                self._console_errors.append(f"[{msg.type}] {msg.text}")

        self.page.on("console", on_console)

    async def navigate(self, path: str):
        from llm_common.agents import NavigationError
        url = f"{self.base_url}{path}"
        try:
            await self.page.goto(url, wait_until="networkidle")
        except Exception as e:
            raise NavigationError(f"Navigation to {url} failed: {e}")

    async def click(self, target: str):
        from llm_common.agents import ElementNotFoundError
        try:
            await self.page.click(target, timeout=5000)
        except Exception as e:
            raise ElementNotFoundError(f"Click failed: {target}")

    async def type_text(self, selector: str, text: str):
        await self.page.fill(selector, text)

    async def screenshot(self) -> str:
        import base64
        screenshot_bytes = await self.page.screenshot(type="png", quality=80)
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    async def get_console_errors(self) -> list[str]:
        errors = self._console_errors.copy()
        self._console_errors.clear()
        return errors

    async def get_network_errors(self) -> list[dict]:
        errors = self._network_errors.copy()
        self._network_errors.clear()
        return errors

    async def wait_for_selector(self, selector: str, timeout_ms: int = 5000):
        await self.page.wait_for_selector(selector, timeout=timeout_ms)

    async def get_current_url(self) -> str:
        return self.page.url

    async def close(self):
        await self.page.close()
```

### 4. Create Runner Script

Create `scripts/e2e_agent/run_smoke.py`:

```python
import asyncio
import os
from llm_common import GLMClient, GLMConfig
from llm_common.agents import UISmokeAgent, load_stories_from_directory
from browser_adapter import MyPlaywrightAdapter
from playwright.async_api import async_playwright

async def main():
    # Initialize GLM client
    api_key = os.environ["ZAI_API_KEY"]
    glm = GLMClient(GLMConfig(api_key=api_key))

    # Load stories
    stories = load_stories_from_directory("docs/TESTING/STORIES")

    # Create browser
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()
    adapter = MyPlaywrightAdapter(page, os.environ["BASE_URL"])

    # Run agent
    agent = UISmokeAgent(glm, adapter, os.environ["BASE_URL"])

    for story in stories:
        result = await agent.run_story(story)
        print(f"{story.id}: {result.status}")
        for error in result.errors:
            print(f"  [{error.severity}] {error.message}")

    await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### 5. Run Tests

```bash
export ZAI_API_KEY="your-api-key"
export BASE_URL="https://app.example.com"

python scripts/e2e_agent/run_smoke.py
```

## Personas and Stories

### How They Work Together

**Personas** define WHO is testing (retail investor, new user, admin) and reference environment variables for credentials. They do NOT contain actual secrets.

**Stories** define WHAT to test (login flow, dashboard load) and reference a persona by ID. The persona provides context to GLM-4.6V about user behavior.

### Persona Schema Example

Create `docs/TESTING/PERSONAS/retail-investor.yml`:

```yaml
id: retail-investor
description: "Cautious retail investor exploring their portfolio with existing linked accounts"

env_mapping:
  email_env: RETAIL_INVESTOR_EMAIL
  clerk_id_env: RETAIL_INVESTOR_CLERK_ID
  password_env: RETAIL_INVESTOR_PASSWORD

plaid_profile:
  institution_id: ins_109508  # Chase sandbox
  username: user_good
  password: pass_good
  mode: basic_sandbox

metadata:
  tags: ["core-flow", "portfolio"]
```

### Loading Personas

```python
from llm_common.agents import load_persona_from_yaml, load_personas_from_directory

# Load single persona
persona = load_persona_from_yaml("docs/TESTING/PERSONAS/retail-investor.yml")

# Load all personas
personas = load_personas_from_directory("docs/TESTING/PERSONAS")

# Resolve credentials at runtime (repo-specific bootstrap)
email = os.environ[persona.env_mapping.email_env]  # Gets RETAIL_INVESTOR_EMAIL
```

### Story + Persona Integration

Stories reference personas by description (not ID):

```yaml
id: story-dashboard-advisor
persona: "Cautious retail investor exploring their portfolio"  # Matches persona.description

steps:
  - id: step-1-verify-accounts
    description: |
      Verify dashboard shows linked Chase account with holdings.
    exploration_budget: 2
```

The persona description is sent to GLM-4.6V as context in the system prompt, influencing how the agent behaves.

### Why No Secrets in Schemas?

- **Version control safe**: Personas can be committed to git
- **Environment-specific**: Same persona works across dev/staging/prod with different env vars
- **Security**: Secrets stay in Railway/CI, not in code
- **Reusability**: Personas are templates, credentials are runtime values

## Tool System

### Standard Tools

The agent provides these tools to GLM-4.6V by default (from `llm_common.agents.prompts.STANDARD_TOOLS`):

1. **navigate**: Navigate to relative path (e.g., `/dashboard`)
2. **click**: Click element by CSS selector or visible text (e.g., `text=Sign In`)
3. **type_text**: Type text into input field (e.g., email, password)
4. **wait_for_element**: Wait for element to appear before continuing
5. **complete_step**: Mark current step as complete and move to next

### Custom Tools

Repos can add app-specific tools using the `custom_tools` parameter:

```python
from llm_common.agents import UISmokeAgent, STANDARD_TOOLS
from llm_common.agents.prompts import build_login_persona_tool

# Define custom tool for backend-assisted login
login_tool = build_login_persona_tool("retail-investor", "Login using test persona credentials")

# Or define your own
custom_tools = [
    {
        "type": "function",
        "function": {
            "name": "verify_plaid_link",
            "description": "Verify Plaid account is linked and active",
            "parameters": {
                "type": "object",
                "properties": {
                    "institution_name": {"type": "string"}
                },
                "required": ["institution_name"],
            },
        },
    }
]

# Agent uses STANDARD_TOOLS + custom_tools
agent = UISmokeAgent(glm, browser, base_url, custom_tools=custom_tools)
```

### Tool Execution Flow

1. GLM receives screenshot + step description + available tools
2. GLM decides which tool to call with what arguments
3. Agent receives tool call, executes via BrowserAdapter
4. Agent sends tool result back to GLM
5. GLM continues or calls `complete_step`

### Example Tool Call

```json
{
  "id": "tc_1",
  "function": {
    "name": "type_text",
    "arguments": "{\"selector\": \"#email\", \"text\": \"test@example.com\"}"
  }
}
```

Agent executes: `await browser.type_text("#email", "test@example.com")`

## GLM Coding Endpoint

### Why We Use the Coding Endpoint

**Endpoint**: `https://api.z.ai/api/coding/paas/v4/chat/completions`

**Reasons**:
1. **Unlimited calls**: Z.AI Coding Plan has no rate limits or balance requirements
2. **No billing**: Free for coding use cases (vs. general endpoint which requires balance)
3. **Same model**: `glm-4.6v` with full vision + tool calling capabilities
4. **Production-ready**: Stable endpoint for long-running automation tasks

**General endpoint** (`https://api.z.ai/api/paas/v4/chat/completions`) requires pre-paid balance and is metered per request. For CI/CD and smoke testing, the coding endpoint is the correct choice.

### Configuration

```python
from llm_common import GLMClient, GLMConfig

config = GLMConfig(
    api_key=os.environ["ZAI_API_KEY"],
    base_url="https://api.z.ai/api/coding/paas/v4",  # Coding endpoint (default)
    default_model="glm-4.6v",
)
client = GLMClient(config)
```

The coding endpoint is **already the default** in `GLMConfig`, so you typically don't need to specify it.

## When to Run Smoke Tests

### Milestone / Weekly Cadence

This agent is designed for **milestone-triggered or weekly smoke tests**, NOT per-PR CI.

**Why not per-PR?**
- **Token cost**: Vision + tool calling uses 500-1000 tokens per step (5000+ per story)
- **Execution time**: Real browser automation takes 30-60 seconds per step
- **Failure noise**: UI changes break tests frequently; too noisy for every PR
- **Intended use**: Validate critical journeys after deployments, not incremental code changes

**Recommended triggers**:
- ✅ Weekly scheduled runs (Sunday night, pre-deployment)
- ✅ Release milestones (before pushing to prod)
- ✅ Post-deployment validation (staging → prod)
- ✅ Manual workflow dispatch (on-demand testing)
- ❌ Every PR commit (too expensive and noisy)
- ❌ Pre-merge checks (too slow)

### GitHub Actions Example

```yaml
name: E2E Smoke Tests

on:
  schedule:
    - cron: "0 2 * * 0"  # Weekly on Sunday 2am UTC
  workflow_dispatch:      # Manual trigger
  # NOT: push, pull_request

jobs:
  smoke-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run smoke tests
        run: python scripts/e2e_agent/run_smoke.py
        env:
          ZAI_API_KEY: ${{ secrets.ZAI_API_KEY }}
          BASE_URL: ${{ secrets.STAGING_URL }}
```

## Token Usage Best Practices

### Cost Per Run

GLM-4.6V vision requests are expensive compared to text-only:

- **Text message**: ~50-100 tokens
- **Screenshot (PNG, 1920x1080)**: ~2000-3000 tokens
- **Tool call + result**: ~100-200 tokens
- **Single step (1 screenshot + 3 tool calls)**: ~3000-4000 tokens
- **Single story (3 steps)**: ~10,000-15,000 tokens

With unlimited coding endpoint calls, **tokens are not billed**, but they still consume API capacity and affect latency.

### Optimization Strategies

#### 1. Limit Number of Stories

Run only **critical user journeys** (3-5 stories max per run):
- Login → Dashboard
- Plaid link flow
- Advisor interaction
- Portfolio view
- Settings update

Don't test every edge case. Focus on **smoke**, not comprehensive E2E.

#### 2. Reduce Screenshot Size

Use smaller viewport or reduce quality:

```python
# In BrowserAdapter.__init__
await page.set_viewport_size({"width": 1280, "height": 720})  # Smaller than 1920x1080

# In screenshot()
screenshot_bytes = await page.screenshot(type="png", quality=75)  # JPEG only
# Note: PNG doesn't support quality, use JPEG if quality control needed
```

Smaller screenshots = fewer tokens = faster responses.

#### 3. Keep Exploration Budgets Low

Set `exploration_budget: 0` for most steps:

```yaml
steps:
  - id: step-1-login
    description: "Navigate to /login and authenticate"
    exploration_budget: 0  # No exploration, just complete the step

  - id: step-2-verify-dashboard
    description: "Verify dashboard loaded with account data"
    exploration_budget: 1  # Allow 1 extra action to check for errors
```

Higher budgets → more tool calls → more tokens.

#### 4. Use Efficient Tool Definitions

Provide clear, concise tool descriptions. Avoid verbose parameter descriptions:

```python
# Bad (verbose)
{
    "description": "This tool allows you to navigate to a different page within the application by providing a relative path starting with a forward slash, for example /dashboard or /settings"
}

# Good (concise)
{
    "description": "Navigate to a path relative to base URL (e.g., /dashboard)"
}
```

#### 5. Batch Stories Efficiently

Run related stories together (same environment, same persona):

```python
# Group stories by persona to reuse session
retail_stories = [s for s in stories if s.persona == "Cautious retail investor"]
new_user_stories = [s for s in stories if s.persona == "New user"]

for story in retail_stories:
    result = await agent.run_story(story)

# Browser context stays warm, faster execution
```

### Monitoring Usage

Track token usage with GLM client metrics:

```python
metrics = glm.get_metrics()
print(f"Total calls: {metrics['total_calls']}")
print(f"Total tokens: {metrics['total_tokens']}")
print(f"Avg tokens/call: {metrics['total_tokens'] / metrics['total_calls']:.0f}")
```

Aim for **<50,000 tokens per smoke run** (5-10 stories).

## Report Processing

### From StoryResult to Beads Issues

The agent produces structured `StoryResult` objects containing errors. Repos implement reporter scripts to convert these to Beads issues.

### StoryResult Structure

```python
@dataclass
class StoryResult:
    story_id: str
    status: str  # "pass", "fail", "partial"
    step_results: list[StepResult]
    errors: list[AgentError]  # All errors across all steps
    metadata: dict[str, Any]
```

### AgentError Structure

```python
@dataclass
class AgentError:
    type: str  # "ui_error", "api_5xx", "console_error", "navigation_error"
    severity: str  # "blocker", "high", "medium", "low"
    message: str
    url: str | None
    details: dict[str, Any]
    step_id: str | None
```

### Reporter Script Pattern

Repos implement `process_report.py` to convert errors to issues:

```python
import json
import subprocess
from collections import defaultdict

def process_report(report_path: str):
    """Convert smoke report to Beads issues."""
    with open(report_path) as f:
        report = json.load(f)

    # Group errors by type to deduplicate
    error_groups = defaultdict(list)
    for result in report["story_results"]:
        for error in result["errors"]:
            key = (error["type"], error["message"])
            error_groups[key].append(error)

    # Create one issue per unique error
    for (error_type, message), occurrences in error_groups.items():
        severity = occurrences[0]["severity"]
        priority = {"blocker": 1, "high": 2, "medium": 3, "low": 4}[severity]

        # Build issue description
        desc = f"**Error Type**: {error_type}\n\n"
        desc += f"**Message**: {message}\n\n"
        desc += f"**Occurrences**: {len(occurrences)}\n\n"
        for occ in occurrences:
            desc += f"- Step: {occ['step_id']}, URL: {occ.get('url', 'N/A')}\n"

        # Create Beads issue
        subprocess.run([
            "bd", "create",
            f"[Smoke Test] {message[:80]}",  # Title
            "--type", "bug",
            "--priority", str(priority),
            "--description", desc,
            "--label", "smoke-test",
        ])

if __name__ == "__main__":
    process_report("smoke_report.json")
```

### Deduplication Strategy

- **Group by (type, message)**: Same error in multiple steps = one issue
- **Include occurrences**: List all steps/URLs where error appeared
- **Map severity to priority**: blocker=1, high=2, medium=3, low=4
- **Add labels**: `smoke-test`, `ui`, `api`, etc.

### When to Create Issues

**Always create** if:
- `severity` is `blocker` or `high`
- Error is new (not already tracked in Beads)

**Consider skipping** if:
- `severity` is `low` and expected (e.g., vendor console warnings)
- Error is known and already has open issue

### Reporter Lives in App Repos

- **llm-common** provides: `AgentError`, `StoryResult`, `SmokeRunReport` models
- **App repos** implement: Reporter script, deduplication logic, Beads integration

This allows each repo to customize how errors map to issues based on their workflow.

## API Reference

### UISmokeAgent

```python
class UISmokeAgent:
    def __init__(
        self,
        glm_client: GLMClient,
        browser: BrowserAdapter,
        base_url: str,
        max_tool_iterations: int = 10,
        custom_tools: list[dict[str, Any]] | None = None,
    ): ...

    async def run_story(self, story: Story) -> StoryResult: ...
```

**Parameters**:
- `glm_client`: GLM-4.6V client for vision + tool calling
- `browser`: BrowserAdapter implementation (Playwright, Selenium, etc.)
- `base_url`: Base URL for the application under test
- `max_tool_iterations`: Max tool calls per step (default 10, prevents infinite loops)
- `custom_tools`: Optional app-specific tools beyond STANDARD_TOOLS

**Responsibilities**:
- Executes story steps sequentially
- Takes screenshots and sends to GLM-4.6V
- Provides tools (STANDARD_TOOLS + custom_tools)
- Executes tool calls via BrowserAdapter
- Monitors for errors (console, network, UI)
- Returns structured StoryResult

### Story Models

```python
@dataclass
class StoryStep:
    id: str
    description: str
    exploration_budget: int = 0  # Extra actions allowed

@dataclass
class Story:
    id: str
    persona: str
    steps: list[StoryStep]
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentError:
    type: str  # "ui_error", "api_5xx", "console_error", etc.
    severity: str  # "blocker", "high", "medium", "low"
    message: str
    url: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    step_id: str | None = None

@dataclass
class StepResult:
    step_id: str
    status: str  # "pass", "fail", "partial"
    actions_taken: list[dict]
    errors: list[AgentError]
    screenshots: list[str]
    duration_ms: int

@dataclass
class StoryResult:
    story_id: str
    status: str  # "pass", "fail", "partial"
    step_results: list[StepResult]
    errors: list[AgentError]
    metadata: dict[str, Any] = field(default_factory=dict)
```

### BrowserAdapter Protocol

```python
class BrowserAdapter(Protocol):
    async def navigate(self, path: str) -> None: ...
    async def click(self, target: str) -> None: ...
    async def type_text(self, selector: str, text: str) -> None: ...
    async def screenshot(self) -> str: ...  # Returns base64 PNG
    async def get_console_errors(self) -> list[str]: ...
    async def get_network_errors(self) -> list[dict]: ...
    async def wait_for_selector(self, selector: str, timeout_ms: int = 5000) -> None: ...
    async def get_current_url(self) -> str: ...
    async def close(self) -> None: ...
```

### Story Loading

```python
from llm_common.agents import (
    load_from_yaml,
    load_from_json,
    load_from_dict,
    load_stories_from_directory,
)

# Load single story
story = load_from_yaml("docs/TESTING/STORIES/my-story.yml")

# Load all stories from directory
stories = load_stories_from_directory("docs/TESTING/STORIES", pattern="*.yml")
```

## Tools Provided to GLM

The agent provides these tools for GLM-4.6V to call:

### navigate

Navigate to a relative path.

```json
{
  "type": "function",
  "function": {
    "name": "navigate",
    "parameters": {
      "properties": {
        "path": {"type": "string"}
      },
      "required": ["path"]
    }
  }
}
```

### click

Click an element by CSS selector or visible text.

```json
{
  "name": "click",
  "parameters": {
    "properties": {
      "target": {"type": "string"}
    }
  }
}
```

### type_text

Type text into an input field.

```json
{
  "name": "type_text",
  "parameters": {
    "properties": {
      "selector": {"type": "string"},
      "text": {"type": "string"}
    }
  }
}
```

### wait_for_element

Wait for element to appear.

```json
{
  "name": "wait_for_element",
  "parameters": {
    "properties": {
      "selector": {"type": "string"},
      "timeout_ms": {"type": "integer"}
    }
  }
}
```

### complete_step

Mark step as complete.

```json
{
  "name": "complete_step",
  "parameters": {}
}
```

## Step Execution Flow

For each story step:

1. **Screenshot**: Capture current page state (base64 PNG, <2MB)
2. **GLM Request**: Send screenshot + step description + persona
3. **Tool Calls**: GLM requests tools (navigate, click, type, etc.)
4. **Execute**: Run tools via BrowserAdapter
5. **Error Check**: Collect console/network errors
6. **Tool Results**: Send back to GLM
7. **Repeat**: Until `complete_step()` or max iterations (10)
8. **Result**: Build StepResult with status, errors, actions

## Error Detection

### Console Errors

Captured via Playwright `console` event:
- `error` and `warning` messages
- Logged as `AgentError` with type `console_error`, severity `medium`

### Network Errors

Captured via Playwright `requestfailed` and `response` events:
- 4xx responses → `api_4xx`, severity `medium`
- 5xx responses → `api_5xx`, severity `high`

### UI Errors

Detected during tool execution:
- `ElementNotFoundError` → `ui_error`, severity `high`
- `NavigationError` → `navigation_error`, severity `blocker`
- `TimeoutError` → `timeout`, severity `high`

### Custom Error Detection

Extend your BrowserAdapter to detect app-specific errors:

```python
async def get_console_errors(self) -> list[str]:
    errors = self._console_errors.copy()

    # Check for app-specific error UI
    error_banner = await self.page.query_selector(".error-banner")
    if error_banner:
        text = await error_banner.text_content()
        errors.append(f"[UI Error Banner] {text}")

    self._console_errors.clear()
    return errors
```

## Production Deployment

### Example: Prime Radiant

See [prime-radiant-ai/docs/TESTING/E2E_AGENT_SPEC.md](https://github.com/stars-end/prime-radiant-ai/tree/main/docs/TESTING/E2E_AGENT_SPEC.md) for:
- Full runner + reporter implementation
- Beads integration (error → `bd create`)
- GitHub Actions workflow
- Story examples (dashboard, Plaid link)

### Example: Affordabot

(To be implemented following Prime Radiant pattern)

## Best Practices

### Story Design

1. **Keep steps atomic**: One clear objective per step
2. **Use exploration_budget wisely**:
   - `0` for critical steps (login, payment)
   - `1-2` for validation steps (check page loaded)
   - `3+` for open-ended exploration
3. **Write defensive descriptions**: "Verify X loaded, check for errors"
4. **Order matters**: Steps run sequentially; ensure prerequisites

### Browser Adapter

1. **Optimize screenshots**: Use `quality=80` to stay under 2MB
2. **Clear error buffers**: `get_console_errors()` should clear after read
3. **Robust selectors**: Support both CSS and `text=...` patterns
4. **Timeout handling**: Use reasonable defaults (5s for clicks, 30s for navigation)

### Running in CI

1. **Use headless mode**: `headless=true` in GitHub Actions
2. **Set viewport**: `1920x1080` for consistency
3. **Artifact retention**: Save reports for 30 days
4. **Don't run on every PR**: Too expensive; use milestone triggers
5. **Monitor GLM usage**: Track token consumption over time

### Security

1. **Never log credentials**: Use `type_text` tool which redacts in logs
2. **Sanitize screenshots**: Avoid capturing PII (credit cards, SSNs)
3. **Test user isolation**: Dedicated test accounts with no real data
4. **Env-specific secrets**: Separate API keys for dev/staging/prod

## Limitations

- **No parallel execution**: Stories run sequentially
- **Single browser context**: All stories share one session
- **No retry logic**: Failures are not retried automatically
- **Vision quality**: GLM may miss subtle UI issues
- **Token usage**: ~500-1000 tokens per step (vision is expensive)

## Troubleshooting

### "Element not found" errors

- **Cause**: Selector changed, slow page load, element not visible
- **Fix**: Use `wait_for_element` tool, update selectors, increase timeout

### "Navigation timeout"

- **Cause**: Slow network, infinite redirects, server down
- **Fix**: Increase navigation timeout in adapter, check network logs

### GLM doesn't call tools

- **Cause**: Ambiguous step description, GLM thinks step is already complete
- **Fix**: Make description more explicit, add "Use tools to..." phrasing

### Too many console errors

- **Cause**: Third-party scripts, vendor warnings
- **Fix**: Filter console errors in adapter (ignore known warnings)

### Screenshots too large

- **Cause**: High-resolution images, large page
- **Fix**: Reduce quality (60-80), resize viewport, clip screenshots

## See Also

- [GLM-4.6V Client](./GLM_CLIENT.md)
- [BrowserAdapter Protocol](../llm_common/agents/browser_adapter.py)
- [Story Loader](../llm_common/agents/story_loader.py)
- [Prime Radiant Implementation](https://github.com/stars-end/prime-radiant-ai/tree/main/docs/TESTING/E2E_AGENT_SPEC.md)
