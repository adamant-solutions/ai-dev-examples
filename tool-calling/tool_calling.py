"""Tool (function) calling with a manual loop: Anthropic Messages API and OpenAI Responses API.

Article: https://tools.adamant-solutions.com/blog/tool-calling-basics/
The model never runs anything: it asks for a tool by name, your code runs it and sends back the result.
"""
import json

# ---------- the tool: plain Python, nothing model-specific ----------

ORDERS = {
    "A-1001": {"status": "shipped", "carrier": "DHL", "eta": "2026-11-03"},
    "A-1002": {"status": "processing", "carrier": None, "eta": None},
}


def get_order_status(order_id: str) -> dict:
    if order_id not in ORDERS:
        raise LookupError(f"no order with id {order_id}")
    return {"order_id": order_id, **ORDERS[order_id]}


# One description, one JSON Schema, reused for both providers.
TOOL_SPECS = [{
    "name": "get_order_status",
    "description": ("Look up the current status of one customer order by its id. "
                    "Returns status (processing, shipped, delivered), carrier and estimated "
                    "delivery date. Order ids look like A-1001. Read-only: it cannot change orders."),
    "schema": {
        "type": "object",
        "properties": {"order_id": {"type": "string", "description": "Order id, e.g. A-1001"}},
        "required": ["order_id"],
        "additionalProperties": False,
    },
}]
HANDLERS = {"get_order_status": get_order_status}


def run_tool(name: str, args: dict) -> tuple[str, bool]:
    """Run a tool the model asked for. Returns (result text, is_error). Never raises:
    errors go back to the model, which can correct itself or explain the problem."""
    handler = HANDLERS.get(name)
    if handler is None:
        return f"unknown tool: {name}", True
    try:
        return json.dumps(handler(**args)), False
    except (LookupError, TypeError, ValueError) as e:
        return f"{type(e).__name__}: {e}", True


class StepLimitExceeded(RuntimeError):
    pass


# ---------- Anthropic Messages API ----------

def anthropic_tools() -> list[dict]:
    return [{"name": t["name"], "description": t["description"],
             "input_schema": t["schema"], "strict": True} for t in TOOL_SPECS]


def ask_claude(client, model: str, question: str, max_steps: int = 5, max_tokens: int = 4096) -> str:
    messages = [{"role": "user", "content": question}]
    for _ in range(max_steps):
        response = client.messages.create(model=model, max_tokens=max_tokens,
                                          tools=anthropic_tools(), messages=messages)
        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text")
        # Keep the whole assistant turn (text, thinking and tool_use blocks) unchanged.
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type == "tool_use":
                text, is_error = run_tool(block.name, block.input)
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": text, "is_error": is_error})
        # All results of one turn go back together, in a single user message.
        messages.append({"role": "user", "content": results})
    raise StepLimitExceeded(f"no final answer after {max_steps} model calls")


# ---------- OpenAI Responses API ----------

def openai_tools() -> list[dict]:
    return [{"type": "function", "name": t["name"], "description": t["description"],
             "parameters": t["schema"], "strict": True} for t in TOOL_SPECS]


def ask_openai(client, model: str, question: str, max_steps: int = 5) -> str:
    items = [{"role": "user", "content": question}]
    for _ in range(max_steps):
        response = client.responses.create(model=model, tools=openai_tools(), input=items)
        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            return response.output_text
        items += response.output
        for call in calls:
            try:
                args = json.loads(call.arguments)  # arguments is a JSON string, not an object
            except json.JSONDecodeError as e:
                text = f"invalid JSON arguments: {e}"
            else:
                text, _ = run_tool(call.name, args)
            items.append({"type": "function_call_output", "call_id": call.call_id, "output": text})
    raise StepLimitExceeded(f"no final answer after {max_steps} model calls")
