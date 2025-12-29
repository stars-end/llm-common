# StreamEvent Contract

**Schema:** [`stream_event.v1.json`](../../llm_common/contracts/schemas/stream_event.v1.json)

The `StreamEvent` contract is a standardized format for events yielded during a streaming execution, such as from an LLM agent or a long-running tool. It provides a consistent structure for different types of data chunks sent over a stream.

## Structure

The event has a simple, flexible structure:

- `type` (string, required): An identifier for the type of event (e.g., `log`, `tool_call`, `tool_result`, `final_answer`).
- `data` (any, required): The payload of the event. The structure of the data depends on the `type`.

## Example Event Sequences

Below are examples of how `StreamEvent` might be used in a hypothetical agent execution flow.

### Example 1: Simple Log Message

This is the most basic event type, used for sending status updates or debugging information.

```json
{
  "type": "log",
  "data": {
    "level": "info",
    "message": "Starting web search for 'latest AI research'."
  }
}
```

### Example 2: Tool Call and Result

This sequence shows the agent deciding to call a tool and then receiving the result.

**Event 1: Tool Call**

```json
{
  "type": "tool_call",
  "data": {
    "tool_name": "web_search",
    "tool_args": {
      "query": "latest AI research"
    }
  }
}
```

**Event 2: Tool Result**

```json
{
  "type": "tool_result",
  "data": {
    "tool_name": "web_search",
    "result": [
      {"source": "https://arxiv.org/abs/2305.18248", "content": "..."}
    ]
  }
}
```

### Example 3: Streaming a Final Answer

This sequence shows a final answer being streamed back to the client in chunks.

**Event 1: Start of Answer**

```json
{
  "type": "answer_chunk",
  "data": {
    "text": "Based on the latest research, the most significant "
  }
}
```

**Event 2: Middle of Answer**

```json
{
  "type": "answer_chunk",
  "data": {
    "text": "breakthroughs have been in the area of large language "
  }
}
```

**Event 3: End of Answer**

```json
{
  "type": "answer_chunk",
  "data": {
    "text": "model efficiency."
  }
}
```

### Example 4: Final Answer with Provenance

This event provides the complete final answer along with its sources. It would typically be the last event in a stream.

```json
{
  "type": "final_answer",
  "data": {
    "text": "Based on the latest research, the most significant breakthroughs have been in the area of large language model efficiency.",
    "provenance": [
      {"source": "https://arxiv.org/abs/2305.18248", "content": "..."}
    ]
  }
}
```
