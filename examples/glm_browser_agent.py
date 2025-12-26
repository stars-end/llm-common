"""GLM-4.6V browser automation example.

This demonstrates using GLM-4.6V for agentic UI testing with:
- Vision: analyzing screenshots
- Tool calling: deciding which browser actions to take
- Multi-turn loops: executing actions and observing results

This pattern is suitable for:
- Prod smoke testing with visual verification
- UI regression testing
- End-user journey validation
"""

import base64
import json
import os
from typing import Any


def main() -> None:
    """Run a simple browser automation scenario with GLM-4.6V."""
    from llm_common import GLMClient, GLMConfig

    # Initialize client
    api_key = os.environ.get("ZAI_API_KEY")
    if not api_key:
        print("Error: ZAI_API_KEY environment variable not set")
        return

    config = GLMConfig(api_key=api_key, default_model="glm-4.6v")
    client = GLMClient(config)

    # Define browser action tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "click_button",
                "description": "Click a button or link on the page",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "button_text": {
                            "type": "string",
                            "description": "Visible text on the button/link",
                        }
                    },
                    "required": ["button_text"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "type_text",
                "description": "Type text into an input field",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "field_label": {"type": "string", "description": "Label of the input field"},
                        "text": {"type": "string", "description": "Text to type"},
                    },
                    "required": ["field_label", "text"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "navigate",
                "description": "Navigate to a URL",
                "parameters": {
                    "type": "object",
                    "properties": {"url": {"type": "string", "description": "URL to navigate to"}},
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "verify_element",
                "description": "Verify an element is visible on the page",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "element_description": {
                            "type": "string",
                            "description": "Description of what to verify",
                        }
                    },
                    "required": ["element_description"],
                },
            },
        },
    ]

    # Simulate a user story: Login flow
    print("\n=== User Story: Test Login Flow ===\n")

    # Step 1: Initial screenshot analysis
    # (In real scenario, this would be a base64-encoded screenshot from Playwright)
    # For demo, we use a minimal 1x1 red pixel PNG
    red_pixel_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a QA agent testing a web application. "
                "You will receive screenshots and must use the provided tools to interact with the page. "
                "Your goal is to complete the user story: verify the login flow works correctly."
            ),
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Current step: Navigate to the login page and verify the form is visible.\n"
                        "Available actions: navigate, click_button, type_text, verify_element.\n"
                        "The screenshot shows the current state of the page."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{red_pixel_b64}"},
                },
            ],
        },
    ]

    print("Sending initial request to GLM-4.6V with screenshot...")
    response = client.chat_with_tools(messages, tools)

    print(f"Assistant: {response['content']}")

    if response["tool_calls"]:
        print(f"\nTool calls: {len(response['tool_calls'])}")
        for tc in response["tool_calls"]:
            func_name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            print(f"  - {func_name}({args})")

            # In a real scenario, you'd execute the tool and capture the result
            # For demo, we simulate a successful execution
            tool_result = f"Successfully executed {func_name} with args {args}"

            # Add assistant message + tool result to conversation
            messages.append(
                {
                    "role": "assistant",
                    "content": response["content"],
                    "tool_calls": response["tool_calls"],
                }
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": func_name,
                    "content": tool_result,
                }
            )

        # Continue conversation after tool execution
        print("\nSending tool results back to GLM-4.6V...")
        followup = client.chat(messages)
        print(f"\nAssistant (after tool execution): {followup.choices[0].message['content']}")

    # Show metrics
    metrics = client.get_metrics()
    print(f"\n=== Metrics ===")
    print(f"Total API calls: {metrics['total_calls']}")
    print(f"Total tokens used: {metrics['total_tokens']}")


def real_world_example() -> None:
    """More realistic example with Playwright integration.

    This shows how you'd integrate GLM-4.6V with a real browser driver.
    """
    print("\n=== Real-World Integration Pattern ===\n")
    print("For production use, integrate with Playwright/Selenium:")
    print()
    print("```python")
    print("from playwright.async_api import async_playwright")
    print("from llm_common import GLMClient, GLMConfig")
    print()
    print("async def run_agent_test(user_story: dict):")
    print("    async with async_playwright() as p:")
    print("        browser = await p.chromium.launch()")
    print("        page = await browser.new_page()")
    print()
    print("        # Initialize GLM client")
    print("        client = GLMClient(GLMConfig(api_key=os.environ['ZAI_API_KEY']))")
    print()
    print("        # Navigate to starting URL")
    print("        await page.goto(user_story['start_url'])")
    print()
    print("        # Main agent loop")
    print("        messages = [{'role': 'system', 'content': user_story['instructions']}]")
    print()
    print("        for step in user_story['steps']:")
    print("            # Capture screenshot")
    print("            screenshot_bytes = await page.screenshot()")
    print("            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()")
    print()
    print("            # Ask GLM what to do")
    print("            messages.append({")
    print("                'role': 'user',")
    print("                'content': [")
    print("                    {'type': 'text', 'text': step['description']},")
    print("                    {'type': 'image_url', 'image_url': {")
    print("                        'url': f'data:image/png;base64,{screenshot_b64}'")
    print("                    }}")
    print("                ]")
    print("            })")
    print()
    print("            response = client.chat_with_tools(messages, tools)")
    print()
    print("            # Execute tool calls via Playwright")
    print("            if response['tool_calls']:")
    print("                for tc in response['tool_calls']:")
    print("                    result = await execute_tool(page, tc)")
    print("                    # Add result to conversation...")
    print()
    print("        await browser.close()")
    print("```")
    print()


if __name__ == "__main__":
    main()
    real_world_example()
