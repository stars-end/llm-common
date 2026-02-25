# Prime Radiant V2 - First Assistant Response
## Story ID: pr_v2_03_first_response
## Category: user_story
## Phase: 3
## Description: Validate first assistant response render path

async def run(verifier):
    """Validate first assistant response render behavior."""
    await verifier.page.goto("https://frontend-dev-f8a3.up.railway.app/v2")
    await verifier.page.wait_for_selector(".cockpit-shell", timeout=10000)
    
    # Send a message to trigger response
    composer_input = await verifier.page.wait_for_selector(".composer-input", timeout=5000)
    await composer_input.fill("Test message for response validation")
    send_button = await verifier.page.wait_for_selector(".send-button", timeout=3000)
    await send_button.click()
    
    # Wait for thinking state
    await verifier.page.wait_for_selector(".message-bubble.thinking", timeout=10000)
    
    # Wait for answer to appear
    await verifier.page.wait_for_selector(".message-bubble.answer", timeout=15000)
    
    # Check for evidence/provenance surface
    evidence_selector = await verifier.page.query_selector(".evidence-provenance")
    if evidence_selector:
        await verifier.page.wait_for_selector(".evidence-item", timeout=5000)