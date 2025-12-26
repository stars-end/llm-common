# GLM-4.6V Client

GLM-4.6V client for vision-powered browser automation and agentic UI testing.

**Version**: 1.0.0
**Status**: Stable
**Last Updated**: 2025-12-11

## Changelog

### v1.0.0 (2025-12-11)

**Initial stable release** - Production-ready GLM-4.6V integration

- ✅ Chat completion (text)
- ✅ Tool calling with JSON schema
- ✅ Vision support (screenshots/images)
- ✅ Multi-turn conversations with tool results
- ✅ Error handling (rate limits, timeouts, API errors)
- ✅ Retry logic with exponential backoff
- ✅ Metrics tracking (total_calls, total_tokens)

**API Endpoint**: `https://api.z.ai/api/coding/paas/v4/chat/completions`
**Model**: `glm-4.6v`
**Compatibility**: Z.AI Coding Plan (unlimited calls)

**Breaking Changes**: None (initial release)

---

## Overview

`GLMClient` provides native access to GLM-4.6V's vision and tool-calling capabilities, designed for:

- **Browser automation**: Screenshot → reasoning → tool call → action
- **UI testing**: Visual verification of application state
- **Agentic workflows**: Multi-turn exploration with LLM decision-making

Unlike the base `LLMClient` abstraction (text-only), `GLMClient` operates directly on the GLM API to support multi-modal input and structured tool execution.

## Installation

```python
from llm_common import GLMClient, GLMConfig
```

## Quick Start

### Basic Chat

```python
import os
from llm_common import GLMClient, GLMConfig

config = GLMConfig(api_key=os.environ["ZAI_API_KEY"])
client = GLMClient(config)

messages = [{"role": "user", "content": "Hello, world!"}]
response = client.chat(messages)

print(response.choices[0].message["content"])
```

### Vision + Tool Calling

```python
# Define browser action tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "click_button",
            "description": "Click a button on the page",
            "parameters": {
                "type": "object",
                "properties": {
                    "button_text": {"type": "string"}
                },
                "required": ["button_text"],
            },
        },
    }
]

# Send screenshot + question
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "Click the login button"},
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,iVBORw0K..."}
            }
        ]
    }
]

response = client.chat_with_tools(messages, tools)

if response["tool_calls"]:
    for tc in response["tool_calls"]:
        print(f"Tool: {tc['function']['name']}")
        print(f"Args: {tc['function']['arguments']}")
```

## API Reference

### GLMConfig

Configuration for GLM client.

```python
config = GLMConfig(
    api_key="...",                                      # Required
    base_url="https://api.z.ai/api/coding/paas/v4",    # Default (coding plan)
    default_model="glm-4.6v",                           # Default
    timeout=60,                                         # Request timeout (seconds)
    max_retries=3,                                      # Retry attempts
    max_tool_iterations=10,                             # Tool loop limit
    screenshot_max_size=2_000_000,                      # 2MB base64 limit
)
```

### GLMClient

#### `chat(messages, model=None, temperature=0.7, max_tokens=None, **kwargs)`

Send chat completion request (no tools).

**Parameters:**
- `messages`: List of message dicts with `role` and `content`
- `model`: Model to use (defaults to `config.default_model`)
- `temperature`: Sampling temperature (0-1)
- `max_tokens`: Max tokens to generate
- `**kwargs`: Additional GLM parameters

**Returns:** `GLMResponse` with `id`, `model`, `choices`, `usage`, `created`

**Raises:**
- `LLMError`: If request fails
- `RateLimitError`: If rate limited
- `TimeoutError`: If request times out

#### `chat_with_tools(messages, tools, model=None, temperature=0.7, max_tokens=None, tool_choice="auto", **kwargs)`

Send chat request with tool calling enabled.

**Parameters:**
- `messages`: List of message dicts
- `tools`: List of tool definitions (GLM function schema)
- `model`: Model to use
- `temperature`: Sampling temperature
- `max_tokens`: Max tokens
- `tool_choice`: `"auto"`, `"required"`, or specific function name
- `**kwargs`: Additional parameters

**Returns:** Dict with:
```python
{
    "content": str,                  # Assistant's text response
    "tool_calls": list[dict] | None, # Tool calls if any
    "finish_reason": str,            # "stop" or "tool_calls"
    "usage": {
        "prompt_tokens": int,
        "completion_tokens": int,
        "total_tokens": int,
    },
    "raw": GLMResponse,              # Full response object
}
```

#### `get_metrics()`

Get client usage metrics.

**Returns:** `{"total_calls": int, "total_tokens": int}`

#### `reset_metrics()`

Reset usage metrics to zero.

## Message Content Types

GLM-4.6V supports multi-modal content:

### Text-only

```python
{"role": "user", "content": "Simple text message"}
```

### Text + Image

```python
{
    "role": "user",
    "content": [
        {"type": "text", "text": "What do you see in this image?"},
        {
            "type": "image_url",
            "image_url": {
                "url": "data:image/png;base64,iVBORw0KGgoAAAA..."
            }
        }
    ]
}
```

### Tool Result

```python
{
    "role": "tool",
    "tool_call_id": "tc_1",
    "name": "click_button",
    "content": "Button clicked successfully"
}
```

## Tool Definition Schema

Tools follow the GLM function schema:

```python
{
    "type": "function",
    "function": {
        "name": "function_name",
        "description": "What this function does",
        "parameters": {
            "type": "object",
            "properties": {
                "param_name": {
                    "type": "string",
                    "description": "Parameter description"
                }
            },
            "required": ["param_name"]
        }
    }
}
```

## Multi-Turn Conversation

GLM-4.6V supports multi-turn tool execution loops:

```python
messages = [
    {"role": "user", "content": "Navigate to example.com and click login"}
]

for _ in range(config.max_tool_iterations):
    response = client.chat_with_tools(messages, tools)

    if not response["tool_calls"]:
        # No more tools to execute
        print(f"Done: {response['content']}")
        break

    # Add assistant message with tool calls
    messages.append({
        "role": "assistant",
        "content": response["content"],
        "tool_calls": response["tool_calls"]
    })

    # Execute each tool and append results
    for tc in response["tool_calls"]:
        result = execute_tool_locally(tc)  # Your implementation
        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "name": tc["function"]["name"],
            "content": result
        })
```

## Integration with Playwright

Example integration for browser automation:

```python
import base64
from playwright.async_api import async_playwright
from llm_common import GLMClient, GLMConfig

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        client = GLMClient(GLMConfig(api_key=os.environ["ZAI_API_KEY"]))

        await page.goto("https://example.com")

        # Take screenshot
        screenshot_bytes = await page.screenshot()
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode()

        # Ask GLM what to do
        response = client.chat_with_tools(
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Find and click the login button"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"}
                    }
                ]
            }],
            tools=[...]  # Your browser action tools
        )

        # Execute tool calls via Playwright
        if response["tool_calls"]:
            for tc in response["tool_calls"]:
                if tc["function"]["name"] == "click_button":
                    args = json.loads(tc["function"]["arguments"])
                    await page.click(f"text={args['button_text']}")

        await browser.close()
```

## Best Practices

### 1. Tool Loop Limits

Always set `max_tool_iterations` to prevent infinite loops:

```python
config = GLMConfig(api_key="...", max_tool_iterations=10)
```

### 2. Screenshot Size

Keep base64 screenshots under 2MB:

```python
# With Playwright
screenshot_bytes = await page.screenshot(quality=80)  # Reduce quality if needed
```

### 3. Error Handling

Wrap API calls in try/except:

```python
from llm_common.core import LLMError, RateLimitError, TimeoutError

try:
    response = client.chat_with_tools(messages, tools)
except RateLimitError as e:
    # Back off and retry
    time.sleep(60)
except TimeoutError:
    # Increase timeout in config
    pass
except LLMError as e:
    # Log and handle generic errors
    logger.error(f"GLM error: {e}")
```

### 4. Metrics Tracking

Monitor API usage:

```python
metrics = client.get_metrics()
print(f"Calls: {metrics['total_calls']}, Tokens: {metrics['total_tokens']}")

if metrics["total_tokens"] > 1_000_000:
    client.reset_metrics()
```

## Limitations

- **No async support**: `GLMClient` is synchronous (uses `urllib.request`)
- **No streaming**: Tool calling requires full responses
- **Vision model only**: Optimized for GLM-4.6V, not text-only models

## Examples

See `examples/glm_browser_agent.py` for a complete working example.

## Comparison with ZaiClient

| Feature | ZaiClient | GLMClient |
|---------|-----------|-----------|
| Base class | `LLMClient` | Standalone |
| Content types | Text only | Text + vision |
| Tool calling | No | Yes |
| Async | Yes | No |
| Budget tracking | Yes | No |
| Use case | General chat | Browser automation |

For text-only chat with budget tracking, use `ZaiClient`.
For vision + tools (browser automation), use `GLMClient`.

## Troubleshooting

### "Insufficient balance" error

Make sure you're using the coding endpoint:

```python
config = GLMConfig(
    api_key="...",
    base_url="https://api.z.ai/api/coding/paas/v4"  # Coding plan
)
```

### Tool calls not returned

Check `tool_choice` parameter:

```python
response = client.chat_with_tools(
    messages,
    tools,
    tool_choice="auto"  # or "required" to force tool use
)
```

### Image too large

Compress before base64 encoding:

```python
from PIL import Image
import io

img = Image.open("screenshot.png")
img = img.resize((img.width // 2, img.height // 2))  # Reduce size
buffer = io.BytesIO()
img.save(buffer, format="PNG", optimize=True)
screenshot_b64 = base64.b64encode(buffer.getvalue()).decode()
```

## See Also

- [GLM-4.6V Documentation](https://docs.z.ai/guides/vlm/glm-4.6v)
- [Example: Browser Agent](../examples/glm_browser_agent.py)
- [Core LLM Client](./CORE_CLIENT.md)
