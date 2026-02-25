# Prime Radiant V2 - Composer Chat Flow
## Story ID: pr_v2_02_composer_chat
## Category: user_story
## Phase: 2
## Description: Validate composer input/send flow for advisor chat

async def run(verifier):
    """Test composer input and send flow."""
    await verifier.page.goto("https://frontend-dev-f8a3.up.railway.app/v2")
    await verifier.page.wait_for_selector(".cockpit-shell", timeout=10000)
    
    # Find and use composer input
    composer_input = await verifier.page.wait_for_selector(".composer-input", timeout=5000)
    await composer_input.fill("Test message for advisor chat")
    
    # Send the message
    send_button = await verifier.page.wait_for_selector(".send-button", timeout=3000)
    await send_button.click()
    
    # Wait for response to start rendering
    await verifier.page.wait_for_selector(".message-bubble.thinking", timeout=10000)