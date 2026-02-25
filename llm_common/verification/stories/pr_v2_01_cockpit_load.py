# Prime Radiant V2 - Cockpit Shell Load
## Story ID: pr_v2_01_cockpit_load
## Category: user_story
## Phase: 1
## Description: Load /v2 and validate cockpit shell is visible

async def run(verifier):
    """Load /v2 and validate cockpit shell visibility."""
    await verifier.page.goto("https://frontend-dev-f8a3.up.railway.app/v2")
    await verifier.page.wait_for_selector(".cockpit-shell", timeout=10000)
    await verifier.page.wait_for_selector(".chat-container", timeout=5000)