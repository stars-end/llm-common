# Agent Skills Integration Guide

This document outlines what durable knowledge should be added to the `agent-skills` repository to support UX Smoke Agent workflows.

## Overview

The agent-skills repository contains reusable skills for AI coding agents working across multiple repos. After implementing the UX Smoke Agent system in llm-common, the following skills should be updated to include persona and Plaid integration knowledge.

## Skill Updates Required

### 1. context-database-schema/SKILL.md

**Add section: Test Persona Creation**

```markdown
## Test Persona Creation

When adding smoke test support to a repo, create test personas in the database for consistent E2E testing.

### Pattern

1. **Define persona schema** in `docs/TESTING/PERSONAS/*.yml`:
   - Use `Persona`, `PersonaEnvMapping`, `PlaidProfile` from llm-common
   - Reference env var names, NOT actual secrets
   - Example: `RETAIL_INVESTOR_EMAIL` instead of "test@example.com"

2. **Bootstrap personas** in migration or seed script:
   - Read environment variables at runtime
   - Create user records in database (Clerk, Supabase, etc.)
   - Store user IDs in environment for test runner

3. **Example persona schema**:
   ```yaml
   id: retail-investor
   description: "Cautious retail investor with existing portfolio"

   env_mapping:
     email_env: RETAIL_INVESTOR_EMAIL
     clerk_id_env: RETAIL_INVESTOR_CLERK_ID
     database_id_env: RETAIL_INVESTOR_DB_ID

   metadata:
     tags: ["core-flow"]
   ```

4. **Example bootstrap**:
   ```python
   import os
   from llm_common.agents import load_persona_from_yaml

   persona = load_persona_from_yaml("docs/TESTING/PERSONAS/retail-investor.yml")

   # Resolve credentials
   email = os.environ[persona.env_mapping.email_env]
   clerk_id = os.environ[persona.env_mapping.clerk_id_env]

   # Create user in database
   user = await db.users.create({
       "email": email,
       "clerk_id": clerk_id,
       "onboarded": True,
   })

   print(f"Created test user: {user.id}")
   ```

### When to Use

- Setting up E2E smoke tests with UISmokeAgent
- Creating consistent test data across environments
- Ensuring test users have proper permissions and state

### Environment Variables

Store in Railway/CI secrets:
- `{PERSONA}_EMAIL`: Test user email
- `{PERSONA}_CLERK_ID`: Clerk user ID (if using Clerk auth)
- `{PERSONA}_DB_ID`: Database user ID (if needed for direct DB setup)
- `{PERSONA}_PASSWORD`: UI login password (if not using backend login helper)
```

### 2. context-plaid-integration/SKILL.md

**Add section: Plaid Sandbox Personas**

```markdown
## Plaid Sandbox Personas for Smoke Tests

UISmokeAgent uses Plaid sandbox profiles to test bank account linking without real credentials.

### Sandbox Institutions

Common Plaid sandbox institutions:
- **Chase**: `ins_109508`
- **Wells Fargo**: `ins_109509`
- **Bank of America**: `ins_109510`
- **Citi**: `ins_109511`

See full list: https://plaid.com/docs/sandbox/test-credentials/

### Sandbox Credentials

Plaid provides public sandbox credentials for different scenarios:

| Username | Password | Behavior |
|----------|----------|----------|
| `user_good` | `pass_good` | Basic success flow |
| `user_transactions_dynamic` | `pass_good` | Dynamic transactions over time |
| `user_mfa_device` | `pass_good` | MFA device selection required |
| `user_mfa_selections` | `pass_good` | MFA multi-selection required |

### Persona Configuration

Define Plaid profiles in persona schemas:

```yaml
id: retail-investor-chase
description: "Retail investor with linked Chase account"

env_mapping:
  email_env: RETAIL_INVESTOR_EMAIL
  clerk_id_env: RETAIL_INVESTOR_CLERK_ID

plaid_profile:
  institution_id: ins_109508  # Chase sandbox
  username: user_good
  password: pass_good
  mode: basic_sandbox
  override_accounts:
    - account_id: "sandbox_account_1"
      balances:
        available: 10000
        current: 10000
```

### Loading Plaid Profiles

```python
from llm_common.agents import load_persona_from_yaml

persona = load_persona_from_yaml("docs/TESTING/PERSONAS/retail-investor-chase.yml")

if persona.plaid_profile:
    institution_id = persona.plaid_profile.institution_id
    username = persona.plaid_profile.username
    password = persona.plaid_profile.password

    # Use in Plaid Link flow or direct API calls
    print(f"Linking {institution_id} with {username}/{password}")
```

### Bootstrap Plaid Links

For personas with Plaid profiles, create link tokens and items during bootstrap:

```python
async def bootstrap_plaid_persona(persona: Persona):
    """Create Plaid link for test persona."""
    if not persona.plaid_profile:
        return

    # Create link token for sandbox
    link_token = await plaid_client.link_token_create({
        "user": {"client_user_id": os.environ[persona.env_mapping.clerk_id_env]},
        "client_name": "Test App",
        "products": ["transactions"],
        "country_codes": ["US"],
        "language": "en",
    })

    # Exchange public token (use Plaid sandbox credentials)
    # This step typically happens in your app's Plaid Link flow
    # For bootstrap, you may need to simulate it via API

    print(f"Link token created for {persona.id}: {link_token['link_token']}")
```

### When to Use

- Testing Plaid Link flows in UISmokeAgent stories
- Creating personas with pre-linked accounts
- Validating transaction sync and balance updates
- Testing MFA flows (device selection, selections)

### Important Notes

- Sandbox credentials are PUBLIC and documented by Plaid
- Never use production Plaid credentials in test personas
- Each sandbox institution has different account structures
- Override accounts to customize balances and holdings
```

### 3. Optional: New Skill for UX Smoke Agent Usage

**Create: context-ux-smoke-agent/SKILL.md**

```markdown
# UX Smoke Agent Usage

Skill for running vision-powered UI smoke tests using GLM-4.6V and UISmokeAgent.

## When to Use

- Setting up weekly/milestone smoke tests for web applications
- Validating critical user journeys (login, dashboard, key flows)
- Detecting UI errors, console errors, and network errors in staging/prod

## Pattern

### 1. Install Dependencies

```bash
cd packages/llm-common
poetry install -E agents

pip install playwright
playwright install chromium
```

### 2. Create Story Specs

Define user journeys in `docs/TESTING/STORIES/*.yml`:

```yaml
id: story-login-dashboard
persona: "New user exploring the application"

steps:
  - id: step-1-login
    description: |
      Navigate to /login and authenticate.
      Verify successful redirect to dashboard.
    exploration_budget: 0

  - id: step-2-verify-dashboard
    description: |
      Verify dashboard loads with user data and no errors.
    exploration_budget: 2

metadata:
  tags: ["core-flow"]
  priority: 1
```

### 3. Create Personas

Define test users in `docs/TESTING/PERSONAS/*.yml` (see context-database-schema for details).

### 4. Implement Browser Adapter

Create Playwright adapter in `scripts/e2e_agent/browser_adapter.py`:

```python
from llm_common.agents import BrowserAdapter, NavigationError, ElementNotFoundError
from playwright.async_api import Page
import base64

class MyPlaywrightAdapter:
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
        url = f"{self.base_url}{path}"
        try:
            await self.page.goto(url, wait_until="networkidle")
        except Exception as e:
            raise NavigationError(f"Failed to navigate to {url}: {e}")

    async def click(self, target: str):
        try:
            await self.page.click(target, timeout=5000)
        except Exception as e:
            raise ElementNotFoundError(f"Click failed: {target}")

    async def type_text(self, selector: str, text: str):
        await self.page.fill(selector, text)

    async def screenshot(self) -> str:
        screenshot_bytes = await self.page.screenshot(type="png")
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

### 5. Create Runner Script

Create `scripts/e2e_agent/run_smoke.py`:

```python
import asyncio
import os
import json
from llm_common import GLMClient, GLMConfig
from llm_common.agents import UISmokeAgent, load_stories_from_directory
from browser_adapter import MyPlaywrightAdapter
from playwright.async_api import async_playwright

async def main():
    api_key = os.environ["ZAI_API_KEY"]
    glm = GLMClient(GLMConfig(api_key=api_key))

    stories = load_stories_from_directory("docs/TESTING/STORIES")

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=True)
    page = await browser.new_page()
    adapter = MyPlaywrightAdapter(page, os.environ["BASE_URL"])

    agent = UISmokeAgent(glm, adapter, os.environ["BASE_URL"])

    results = []
    for story in stories:
        result = await agent.run_story(story)
        results.append(result)
        print(f"{story.id}: {result.status}")

    # Save report
    with open("smoke_report.json", "w") as f:
        json.dump({"story_results": [r.__dict__ for r in results]}, f, indent=2)

    await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### 6. Create Reporter Script

Create `scripts/e2e_agent/process_report.py` to convert errors to Beads issues:

```python
import json
import subprocess
from collections import defaultdict

def process_report(report_path: str):
    with open(report_path) as f:
        report = json.load(f)

    error_groups = defaultdict(list)
    for result in report["story_results"]:
        for error in result["errors"]:
            key = (error["type"], error["message"])
            error_groups[key].append(error)

    for (error_type, message), occurrences in error_groups.items():
        severity = occurrences[0]["severity"]
        priority = {"blocker": 1, "high": 2, "medium": 3, "low": 4}[severity]

        subprocess.run([
            "bd", "create",
            f"[Smoke Test] {message[:80]}",
            "--type", "bug",
            "--priority", str(priority),
            "--description", f"Error: {message}\nOccurrences: {len(occurrences)}",
            "--label", "smoke-test",
        ])

if __name__ == "__main__":
    process_report("smoke_report.json")
```

### 7. Add GitHub Workflow

Create `.github/workflows/e2e-smoke.yml`:

```yaml
name: E2E Smoke Tests

on:
  schedule:
    - cron: "0 2 * * 0"  # Weekly Sunday 2am UTC
  workflow_dispatch:

jobs:
  smoke-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          cd packages/llm-common
          pip install poetry
          poetry install -E agents
          pip install playwright
          playwright install chromium

      - name: Run smoke tests
        run: python scripts/e2e_agent/run_smoke.py
        env:
          ZAI_API_KEY: ${{ secrets.ZAI_API_KEY }}
          BASE_URL: ${{ secrets.STAGING_URL }}

      - name: Process report
        if: failure()
        run: python scripts/e2e_agent/process_report.py
        env:
          BD_TOKEN: ${{ secrets.BD_TOKEN }}

      - name: Upload report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: smoke-report
          path: smoke_report.json
          retention-days: 30
```

## Key Concepts

- **Stories**: User journey specifications (YAML)
- **Personas**: Test user definitions without secrets
- **BrowserAdapter**: Protocol for browser automation (Playwright/Selenium)
- **UISmokeAgent**: GLM-4.6V powered orchestrator
- **Reporter**: Converts errors to Beads issues

## Best Practices

1. **Run weekly or at milestones**, not per-PR (too expensive)
2. **Limit to 3-5 critical stories** per run
3. **Use small screenshots** (1280x720) to reduce tokens
4. **Set exploration_budget: 0** for most steps
5. **Deduplicate errors** before creating issues

## See Also

- [UI Smoke Agent Documentation](../docs/UI_SMOKE_AGENT.md)
- [GLM Client Documentation](../docs/GLM_CLIENT.md)
- [Persona Schema](../llm_common/agents/persona.py)
```

## Implementation Checklist

- [ ] Update `context-database-schema/SKILL.md` with test persona creation section
- [ ] Update `context-plaid-integration/SKILL.md` with Plaid sandbox personas section
- [ ] (Optional) Create `context-ux-smoke-agent/SKILL.md` for complete workflow
- [ ] Test skills with AI coding agents (Claude Code, Codex CLI)
- [ ] Document any repo-specific variations in primary repo docs

## Notes

- Agent-skills is a separate repository from llm-common
- Skills should be updated after llm-common UX Smoke Agent stabilization is complete
- Skills provide durable, searchable knowledge for agents working across repos
