import anthropic
import json

# Initialize the Anthropic client (uses ANTHROPIC_API_KEY env var)
client = anthropic.Anthropic()

# Define the get_weather tool
tools = [
    {
        "name": "get_weather",
        "description": "Get the current temperature for a given city.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "The city name"}},
            "required": ["city"],
        },
    }
]


# Mock implementation of get_weather function
def get_weather(city: str) -> str:
    """In a real system, this would call a weather API."""
    weather_data = {
        "Mumbai": "31°C, sunny",
        "London": "15°C, cloudy",
        "New York": "22°C, partly cloudy",
        "Tokyo": "18°C, rainy",
    }
    return weather_data.get(city, "Unknown city")


initial_message = "What's the weather in Mumbai?"

# Show the request payload
request_payload_step1 = {
    "model": "claude-sonnet-4-6",
    "max_tokens": 1024,
    "tools": tools,
    "messages": [{"role": "user", "content": initial_message}],
}

# Make the first API call
response_step1 = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": initial_message}],
)


# Show the response content
print("\nResponse content (JSON view):")
response_content_step1 = []
for block in response_step1.content:
    if block.type == "text":
        response_content_step1.append({"type": "text", "text": block.text})
    elif block.type == "tool_use":
        response_content_step1.append(
            {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }
        )
print(json.dumps(response_content_step1, indent=2))


# Check for tool use
if response_step1.stop_reason != "tool_use":
    print(
        "\nError: Expected stop_reason to be 'tool_use' but got:",
        response_step1.stop_reason,
    )
    exit(1)

# Extract the tool call details
tool_use_block = None
for block in response_step1.content:
    if block.type == "tool_use":
        tool_use_block = block
        break

if not tool_use_block:
    print("\nError: No tool_use block found in response")
    exit(1)

tool_use_id = tool_use_block.id
tool_name = tool_use_block.name
tool_input = tool_use_block.input


# ============================================================================
# STEP 2: Execute the tool function
# ============================================================================

city = tool_input.get("city")
tool_result = get_weather(city)

# ============================================================================
# STEP 3: Send tool result back to Claude
# ============================================================================

# Build the messages array for the second request
# This includes: original user message + assistant response + tool result
messages_step2 = [
    {"role": "user", "content": initial_message},
    {
        "role": "assistant",
        "content": response_content_step1,  # Replay the exact assistant response
    },
    {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,  # CRITICAL: Match the tool_use_id from step 1
                "content": tool_result,
            }
        ],
    },
]

request_payload_step3 = {
    "model": "claude-sonnet-4-6",
    "max_tokens": 1024,
    "tools": tools,
    "messages": messages_step2,
}

# Make the second API call
response_step3 = client.messages.create(
    model="claude-sonnet-4-6", max_tokens=1024, tools=tools, messages=messages_step2
)

print(f"\nResponse received:")
print(f"  Message ID: {response_step3.id}")
print(f"  Stop reason: {response_step3.stop_reason}")

# Show the response content
print("\nResponse content (final answer):")
for block in response_step3.content:
    if block.type == "text":
        print(f"  Text: {block.text}")

if response_step3.stop_reason != "end_turn":
    print(
        f"\n⚠ Warning: Expected stop_reason 'end_turn' but got '{response_step3.stop_reason}'"
    )
else:
    print(f"\n✓ Stop reason is 'end_turn' — conversation complete")


# ============================================================================
# SUMMARY
# ============================================================================
"""
print(
Step 1 — Initial Request:
  Role: user
  Content: Question about weather in Mumbai
  Stop reason: (user requests don't have stop_reason)

Step 2 — Claude's Tool Request:
  Role: assistant
  Content: Text block + tool_use block with id '{tool_use_id}'
  Stop reason: tool_use ← Your signal to execute the tool

Step 3 — Tool Execution:
  Ran: get_weather(city='Mumbai')
  Result: {tool_result}

Step 4 — Send Tool Result Back:
  Role: user
  Content: tool_result block with tool_use_id='{tool_use_id}'
  (tool_use_id must match the id from Step 2's tool_use block)

Step 5 — Claude's Final Answer:
  Role: assistant
  Content: Text block answering the question
  Stop reason: end_turn ← Turn is complete

KEY POINTS FOR CCA-F:
✓ The tool_use_id and tool_result tool_use_id must match exactly
✓ You must replay the entire assistant message (all blocks) before sending tool_result
✓ Multiple tool results go in one user message's content array (not separate messages)
✓ stop_reason = "tool_use" means run the tool and reply
✓ stop_reason = "end_turn" means the turn is complete
)"""
