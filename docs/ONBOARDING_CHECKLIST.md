# UX Smoke Agent Onboarding Checklist

This checklist guides new repos through adopting the GLM-4.6V powered UX Smoke Agent system for milestone-triggered smoke tests.

## Prerequisites

Before starting, ensure:
- [ ] Your repo has llm-common as a submodule or dependency
- [ ] You have a Z.AI API key with Coding Plan access
- [ ] You have Railway or CI environment for secrets storage
- [ ] You have Beads (bd) set up for issue tracking

## Phase 1: Repository Setup

### 1.1 Install Dependencies

- [ ] Add llm-common to your project:
  ```bash
  # As submodule (recommended)
  git submodule add git@github.com:stars-end/llm-common.git packages/llm-common
  cd packages/llm-common
  git checkout v0.3.0  # Pin to stable release

  # As pip dependency
  pip install -e packages/llm-common[agents]
  ```

- [ ] Install Playwright:
  ```bash
  pip install playwright
  playwright install chromium
  ```

- [ ] Verify imports work:
  ```python
  from llm_common import GLMClient, GLMConfig
  from llm_common.agents import UISmokeAgent, load_stories_from_directory
  ```

### 1.2 Create Directory Structure

- [ ] Create testing directories:
  ```bash
  mkdir -p docs/TESTING/STORIES
  mkdir -p docs/TESTING/PERSONAS
  mkdir -p scripts/e2e_agent
  ```

- [ ] Create `.gitignore` entries:
  ```
  smoke_report.json
  screenshots/
  playwright-report/
  ```

## Phase 2: Define Test Personas

### 2.1 Create Persona Schemas

- [ ] Define 1-3 test personas in `docs/TESTING/PERSONAS/*.yml`:

**Example**: `docs/TESTING/PERSONAS/new-user.yml`
```yaml
id: new-user
description: "New user exploring the application for the first time"

env_mapping:
  email_env: NEW_USER_EMAIL
  clerk_id_env: NEW_USER_CLERK_ID
  password_env: NEW_USER_PASSWORD

metadata:
  tags: ["onboarding"]
```

**Example with Plaid**: `docs/TESTING/PERSONAS/retail-investor.yml`
```yaml
id: retail-investor
description: "Cautious retail investor with linked Chase account"

env_mapping:
  email_env: RETAIL_INVESTOR_EMAIL
  clerk_id_env: RETAIL_INVESTOR_CLERK_ID

plaid_profile:
  institution_id: ins_109508  # Chase sandbox
  username: user_good
  password: pass_good
  mode: basic_sandbox

metadata:
  tags: ["core-flow", "plaid"]
```

- [ ] Validate persona schemas load correctly:
  ```python
  from llm_common.agents import load_personas_from_directory
  personas = load_personas_from_directory("docs/TESTING/PERSONAS")
  print(f"Loaded {len(personas)} personas")
  ```

### 2.2 Bootstrap Test Users

- [ ] Create bootstrap script `scripts/bootstrap_test_users.py`:
  ```python
  import os
  from llm_common.agents import load_personas_from_directory

  async def bootstrap():
      personas = load_personas_from_directory("docs/TESTING/PERSONAS")

      for persona in personas:
          email = os.environ[persona.env_mapping.email_env]

          # Create user in your database (Clerk, Supabase, etc.)
          user = await create_test_user(email)

          print(f"Created test user: {persona.id} -> {user.id}")

  if __name__ == "__main__":
      import asyncio
      asyncio.run(bootstrap())
  ```

- [ ] Run bootstrap locally to verify it works
- [ ] Document required environment variables in repo README

### 2.3 Configure Secrets

- [ ] Add secrets to Railway/CI:
  - [ ] `ZAI_API_KEY` - Z.AI API key
  - [ ] `BASE_URL` - Staging/prod URL
  - [ ] `{PERSONA}_EMAIL` - Test user emails
  - [ ] `{PERSONA}_CLERK_ID` - Clerk IDs (if using Clerk)
  - [ ] `{PERSONA}_PASSWORD` - UI passwords (if needed)
  - [ ] `BD_TOKEN` - Beads token for issue creation (if needed)

## Phase 3: Define User Stories

### 3.1 Write Story Specs

- [ ] Create 3-5 critical user journey stories in `docs/TESTING/STORIES/*.yml`

**Example**: `docs/TESTING/STORIES/story-login-dashboard.yml`
```yaml
id: story-login-dashboard
persona: "New user exploring the application for the first time"

steps:
  - id: step-1-navigate-login
    description: |
      Navigate to /login page.
      Verify login form is visible.
    exploration_budget: 0

  - id: step-2-authenticate
    description: |
      Fill in email and password fields.
      Click the login button.
      Wait for redirect to dashboard.
    exploration_budget: 0

  - id: step-3-verify-dashboard
    description: |
      Verify dashboard loaded successfully.
      Check for welcome message or user data.
      Look for any errors or blank states.
    exploration_budget: 2

metadata:
  tags: ["core-flow", "auth"]
  priority: 1
```

**Example with Plaid**: `docs/TESTING/STORIES/story-plaid-link.yml`
```yaml
id: story-plaid-link
persona: "Cautious retail investor with linked Chase account"

steps:
  - id: step-1-navigate-accounts
    description: |
      Navigate to /accounts or /settings/banking.
      Verify "Link Bank Account" button is visible.
    exploration_budget: 1

  - id: step-2-start-plaid-link
    description: |
      Click "Link Bank Account" button.
      Wait for Plaid Link modal to open.
      Verify institution search is visible.
    exploration_budget: 1

  - id: step-3-select-institution
    description: |
      Search for "Chase" in institution search.
      Click Chase institution.
      Wait for login screen.
    exploration_budget: 0

  - id: step-4-enter-credentials
    description: |
      Enter sandbox username "user_good".
      Enter sandbox password "pass_good".
      Submit credentials.
      Wait for account selection screen.
    exploration_budget: 0

  - id: step-5-complete-link
    description: |
      Select checking account.
      Complete link flow.
      Verify success message and account appears in UI.
    exploration_budget: 2

metadata:
  tags: ["plaid", "banking"]
  priority: 1
```

- [ ] Validate stories load correctly:
  ```python
  from llm_common.agents import load_stories_from_directory
  stories = load_stories_from_directory("docs/TESTING/STORIES")
  print(f"Loaded {len(stories)} stories")
  ```

### 3.2 Story Design Guidelines

- [ ] Each story has 2-5 steps (not too granular, not too broad)
- [ ] Critical steps (login, payment) have `exploration_budget: 0`
- [ ] Validation steps have `exploration_budget: 1-2`
- [ ] Step descriptions are clear and actionable
- [ ] Stories cover 3-5 critical user journeys (not exhaustive E2E)

## Phase 4: Implement Browser Adapter

### 4.1 Create Playwright Adapter

- [ ] Create `scripts/e2e_agent/browser_adapter.py`:

```python
"""Playwright implementation of BrowserAdapter for your application."""

import base64
from playwright.async_api import Page
from llm_common.agents import BrowserAdapter, NavigationError, ElementNotFoundError


class MyPlaywrightAdapter:
    """Playwright adapter for {YOUR_APP_NAME}."""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url.rstrip("/")
        self._console_errors = []
        self._network_errors = []
        self._setup_listeners()

    def _setup_listeners(self):
        """Set up browser event listeners for error detection."""

        def on_console(msg):
            if msg.type in ("error", "warning"):
                self._console_errors.append(f"[{msg.type}] {msg.text}")

        def on_request_failed(request):
            self._network_errors.append({
                "url": request.url,
                "method": request.method,
                "failure": request.failure,
            })

        def on_response(response):
            if response.status >= 400:
                self._network_errors.append({
                    "url": response.url,
                    "method": response.request.method,
                    "status": response.status,
                })

        self.page.on("console", on_console)
        self.page.on("requestfailed", on_request_failed)
        self.page.on("response", on_response)

    async def navigate(self, path: str):
        """Navigate to relative path."""
        url = f"{self.base_url}{path}"
        try:
            await self.page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            raise NavigationError(f"Navigation to {url} failed: {e}")

    async def click(self, target: str):
        """Click element by CSS selector or visible text."""
        try:
            await self.page.click(target, timeout=5000)
        except Exception as e:
            raise ElementNotFoundError(f"Click failed on {target}: {e}")

    async def type_text(self, selector: str, text: str):
        """Type text into input field."""
        try:
            await self.page.fill(selector, text, timeout=5000)
        except Exception as e:
            raise ElementNotFoundError(f"Type text failed on {selector}: {e}")

    async def screenshot(self) -> str:
        """Capture screenshot as base64 PNG."""
        screenshot_bytes = await self.page.screenshot(type="png")
        return base64.b64encode(screenshot_bytes).decode("utf-8")

    async def get_console_errors(self) -> list[str]:
        """Get console errors since last check."""
        errors = self._console_errors.copy()
        self._console_errors.clear()
        return errors

    async def get_network_errors(self) -> list[dict]:
        """Get network errors since last check."""
        errors = self._network_errors.copy()
        self._network_errors.clear()
        return errors

    async def wait_for_selector(self, selector: str, timeout_ms: int = 5000):
        """Wait for element to appear."""
        await self.page.wait_for_selector(selector, timeout=timeout_ms)

    async def get_current_url(self) -> str:
        """Get current page URL."""
        return self.page.url

    async def close(self):
        """Close page."""
        await self.page.close()
```

- [ ] Customize adapter for your app:
  - [ ] Add app-specific error detection (error banners, modals)
  - [ ] Add custom selectors or helpers
  - [ ] Add authentication helpers if needed

### 4.2 Test Adapter Locally

- [ ] Create quick test script `scripts/e2e_agent/test_adapter.py`:
  ```python
  import asyncio
  import os
  from playwright.async_api import async_playwright
  from browser_adapter import MyPlaywrightAdapter

  async def main():
      async with async_playwright() as p:
          browser = await p.chromium.launch(headless=False)
          page = await browser.new_page()
          adapter = MyPlaywrightAdapter(page, os.environ["BASE_URL"])

          await adapter.navigate("/")
          screenshot_b64 = await adapter.screenshot()
          print(f"Screenshot captured: {len(screenshot_b64)} chars")

          await browser.close()

  if __name__ == "__main__":
      asyncio.run(main())
  ```

- [ ] Run test locally to verify adapter works

## Phase 5: Create Runner and Reporter

### 5.1 Create Runner Script

- [ ] Create `scripts/e2e_agent/run_smoke.py`:

```python
"""Main runner for UX smoke tests."""

import asyncio
import json
import os
from datetime import datetime, timezone
from llm_common import GLMClient, GLMConfig
from llm_common.agents import UISmokeAgent, load_stories_from_directory
from browser_adapter import MyPlaywrightAdapter
from playwright.async_api import async_playwright


async def main():
    """Run smoke tests and generate report."""
    print("=== UX Smoke Agent ===")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")

    # Initialize GLM client
    api_key = os.environ["ZAI_API_KEY"]
    glm = GLMClient(GLMConfig(api_key=api_key))

    # Load stories
    stories = load_stories_from_directory("docs/TESTING/STORIES")
    print(f"Loaded {len(stories)} stories")

    # Create browser
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=os.environ.get("HEADLESS", "true") == "true"
    )
    page = await browser.new_page(viewport={"width": 1280, "height": 720})
    adapter = MyPlaywrightAdapter(page, os.environ["BASE_URL"])

    # Create agent
    agent = UISmokeAgent(glm, adapter, os.environ["BASE_URL"])

    # Run stories
    results = []
    for i, story in enumerate(stories, 1):
        print(f"\n[{i}/{len(stories)}] Running story: {story.id}")
        result = await agent.run_story(story)
        results.append(result)
        print(f"  Status: {result.status}")
        print(f"  Errors: {len(result.errors)}")

    # Save report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "story_results": [
            {
                "story_id": r.story_id,
                "status": r.status,
                "errors": [
                    {
                        "type": e.type,
                        "severity": e.severity,
                        "message": e.message,
                        "url": e.url,
                        "step_id": e.step_id,
                        "details": e.details,
                    }
                    for e in r.errors
                ],
                "step_results": [
                    {
                        "step_id": sr.step_id,
                        "status": sr.status,
                        "duration_ms": sr.duration_ms,
                        "actions_taken": sr.actions_taken,
                    }
                    for sr in r.step_results
                ],
            }
            for r in results
        ],
        "metrics": glm.get_metrics(),
    }

    with open("smoke_report.json", "w") as f:
        json.dump(report, f, indent=2)
    print("\nReport saved to smoke_report.json")

    # Print summary
    total_errors = sum(len(r.errors) for r in results)
    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")

    print(f"\n=== Summary ===")
    print(f"Passed: {passed}/{len(results)}")
    print(f"Failed: {failed}/{len(results)}")
    print(f"Total errors: {total_errors}")
    print(f"GLM calls: {report['metrics']['total_calls']}")
    print(f"GLM tokens: {report['metrics']['total_tokens']}")

    await browser.close()
    await playwright.stop()

    # Exit with error code if any story failed
    if failed > 0:
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] Test runner locally:
  ```bash
  export ZAI_API_KEY="your-key"
  export BASE_URL="https://staging.example.com"
  export HEADLESS="false"  # For debugging

  python scripts/e2e_agent/run_smoke.py
  ```

### 5.2 Create Reporter Script

- [ ] Create `scripts/e2e_agent/process_report.py`:

```python
"""Convert smoke report to Beads issues."""

import json
import subprocess
from collections import defaultdict
from pathlib import Path


def process_report(report_path: str = "smoke_report.json"):
    """Convert smoke test errors to Beads issues."""
    if not Path(report_path).exists():
        print(f"Report not found: {report_path}")
        return

    with open(report_path) as f:
        report = json.load(f)

    # Group errors by (type, message) to deduplicate
    error_groups = defaultdict(list)
    for result in report["story_results"]:
        for error in result["errors"]:
            key = (error["type"], error["message"])
            error_groups[key].append(error)

    print(f"Found {len(error_groups)} unique errors")

    # Create one issue per unique error
    for (error_type, message), occurrences in error_groups.items():
        severity = occurrences[0]["severity"]

        # Skip low-severity errors
        if severity == "low":
            print(f"Skipping low severity error: {message[:60]}")
            continue

        priority = {"blocker": 1, "high": 2, "medium": 3, "low": 4}[severity]

        # Build issue description
        desc = f"**Error Type**: {error_type}\n\n"
        desc += f"**Message**: {message}\n\n"
        desc += f"**Severity**: {severity}\n\n"
        desc += f"**Occurrences**: {len(occurrences)}\n\n"

        for occ in occurrences:
            desc += f"- Step: `{occ['step_id']}`, URL: {occ.get('url', 'N/A')}\n"

        # Create Beads issue
        title = f"[Smoke Test] {message[:80]}"
        print(f"Creating issue: {title}")

        try:
            subprocess.run(
                [
                    "bd",
                    "create",
                    title,
                    "--type",
                    "bug",
                    "--priority",
                    str(priority),
                    "--description",
                    desc,
                    "--label",
                    "smoke-test",
                    "--label",
                    error_type,
                ],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"Failed to create issue: {e}")


if __name__ == "__main__":
    process_report()
```

- [ ] Test reporter locally with a sample report

## Phase 6: GitHub Actions Integration

### 6.1 Create Workflow

- [ ] Create `.github/workflows/e2e-smoke.yml`:

```yaml
name: E2E Smoke Tests

on:
  schedule:
    - cron: "0 2 * * 0"  # Weekly on Sunday at 2am UTC
  workflow_dispatch:     # Manual trigger
  # NOT on push or pull_request (too expensive)

jobs:
  smoke-test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          submodules: recursive  # If using submodules

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          cd packages/llm-common
          pip install poetry
          poetry install -E agents
          cd ../..
          pip install playwright
          playwright install chromium

      - name: Run smoke tests
        id: smoke-test
        run: python scripts/e2e_agent/run_smoke.py
        env:
          ZAI_API_KEY: ${{ secrets.ZAI_API_KEY }}
          BASE_URL: ${{ secrets.STAGING_URL }}
          HEADLESS: "true"
          # Add persona env vars
          NEW_USER_EMAIL: ${{ secrets.NEW_USER_EMAIL }}
          NEW_USER_CLERK_ID: ${{ secrets.NEW_USER_CLERK_ID }}
          RETAIL_INVESTOR_EMAIL: ${{ secrets.RETAIL_INVESTOR_EMAIL }}
          RETAIL_INVESTOR_CLERK_ID: ${{ secrets.RETAIL_INVESTOR_CLERK_ID }}

      - name: Process report and create issues
        if: failure()  # Only create issues on failure
        run: python scripts/e2e_agent/process_report.py
        env:
          BD_TOKEN: ${{ secrets.BD_TOKEN }}  # If needed for bd CLI

      - name: Upload smoke report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: smoke-report
          path: smoke_report.json
          retention-days: 30
```

- [ ] Add workflow secrets to GitHub:
  - [ ] `ZAI_API_KEY`
  - [ ] `STAGING_URL`
  - [ ] Persona secrets (`{PERSONA}_EMAIL`, etc.)
  - [ ] `BD_TOKEN` (if needed)

### 6.2 Test Workflow

- [ ] Trigger workflow manually via GitHub Actions UI
- [ ] Verify it runs successfully
- [ ] Check artifacts are uploaded
- [ ] Verify issues are created on failure

## Phase 7: Documentation

### 7.1 Update Repo README

- [ ] Add section on smoke tests:
  ```markdown
  ## Smoke Tests

  This repo uses the UX Smoke Agent for milestone-triggered smoke tests.

  ### Running Locally

  ```bash
  export ZAI_API_KEY="your-key"
  export BASE_URL="https://staging.example.com"
  export NEW_USER_EMAIL="test@example.com"
  # ... other persona env vars

  python scripts/e2e_agent/run_smoke.py
  ```

  ### Adding Stories

  1. Create YAML file in `docs/TESTING/STORIES/`
  2. Reference persona by description
  3. Define 2-5 steps with clear objectives
  4. Set exploration budgets (0 for critical, 1-2 for validation)

  ### See Also

  - [Story Specs](./docs/TESTING/STORIES/)
  - [Persona Schemas](./docs/TESTING/PERSONAS/)
  - [llm-common UI Smoke Agent Docs](./packages/llm-common/docs/UI_SMOKE_AGENT.md)
  ```

### 7.2 Document Environment Variables

- [ ] Create `docs/TESTING/ENVIRONMENT_VARIABLES.md`:
  ```markdown
  # Smoke Test Environment Variables

  ## Required

  - `ZAI_API_KEY` - Z.AI API key with Coding Plan access
  - `BASE_URL` - Application URL to test (staging/prod)

  ## Persona Credentials

  ### New User Persona

  - `NEW_USER_EMAIL` - Test user email
  - `NEW_USER_CLERK_ID` - Clerk user ID
  - `NEW_USER_PASSWORD` - UI login password

  ### Retail Investor Persona

  - `RETAIL_INVESTOR_EMAIL` - Test user email
  - `RETAIL_INVESTOR_CLERK_ID` - Clerk user ID

  ## Optional

  - `HEADLESS` - Run in headless mode (default: `true`)
  - `BD_TOKEN` - Beads token for issue creation
  ```

### 7.3 Create E2E Spec Document

- [ ] Create `docs/TESTING/E2E_AGENT_SPEC.md` documenting:
  - [ ] Architecture overview for your repo
  - [ ] How to add new stories
  - [ ] How to add new personas
  - [ ] Custom tools (if any)
  - [ ] Error handling specifics
  - [ ] Troubleshooting guide

## Phase 8: Validation and Iteration

### 8.1 Initial Validation

- [ ] Run smoke tests locally with 1-2 stories
- [ ] Verify agent can navigate, click, type
- [ ] Verify errors are detected and reported
- [ ] Verify JSON report is generated correctly

### 8.2 CI Validation

- [ ] Trigger GitHub workflow manually
- [ ] Verify workflow completes successfully
- [ ] Check smoke report artifact
- [ ] Verify Beads issues created on failure

### 8.3 Iterate

- [ ] Tune `exploration_budget` based on actual runs
- [ ] Adjust step descriptions if agent gets confused
- [ ] Add custom tools for app-specific actions
- [ ] Filter out noisy console errors in adapter
- [ ] Optimize screenshot size if token usage is high

## Phase 9: Maintenance

### 9.1 Story Maintenance

- [ ] Review stories monthly for relevance
- [ ] Update step descriptions as UI changes
- [ ] Archive or remove obsolete stories
- [ ] Add new stories for new critical flows

### 9.2 Persona Maintenance

- [ ] Refresh test user credentials periodically
- [ ] Add new personas for new user types
- [ ] Update Plaid profiles if sandbox changes

### 9.3 Monitoring

- [ ] Track smoke test pass rate over time
- [ ] Monitor token usage (aim for <50k per run)
- [ ] Review Beads issues created by smoke tests
- [ ] Adjust workflow schedule as needed (weekly vs. bi-weekly)

## Completion Criteria

Your repo is successfully onboarded when:

- [ ] ✅ 3-5 smoke test stories are defined and running
- [ ] ✅ 1-3 test personas are created and bootstrapped
- [ ] ✅ Browser adapter is implemented and tested
- [ ] ✅ GitHub workflow runs weekly without errors
- [ ] ✅ Errors are detected and converted to Beads issues
- [ ] ✅ Documentation is complete and up-to-date
- [ ] ✅ Team understands how to add new stories and personas

## Getting Help

- **llm-common docs**: `packages/llm-common/docs/UI_SMOKE_AGENT.md`
- **GLM client docs**: `packages/llm-common/docs/GLM_CLIENT.md`
- **Reference implementation**: [prime-radiant-ai E2E spec](https://github.com/stars-end/prime-radiant-ai/tree/main/docs/TESTING/E2E_AGENT_SPEC.md)
- **Issues**: Open GitHub issue in llm-common for bugs or questions

## Next Steps

After onboarding:

1. **Monitor first runs**: Watch first few weekly runs closely, adjust as needed
2. **Share learnings**: Document repo-specific patterns for other teams
3. **Contribute back**: Improve llm-common abstractions based on your experience
4. **Expand coverage**: Add more stories as confidence grows

---

**Estimated time to complete**: 4-6 hours for initial setup + 2-4 hours for iteration
