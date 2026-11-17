import json
import re
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Ticket(BaseModel):
    """What we want the model to return for each support message."""

    # extra="forbid": a field we did not ask for is an error, not silently dropped.
    # strict=True: "3" is not accepted for an int, true/false only for a bool.
    model_config = ConfigDict(extra="forbid", strict=True)

    category: Literal["billing", "bug", "feature", "other"]
    priority: int = Field(ge=1, le=5)
    summary: str = Field(min_length=1, max_length=120)
    needs_human: bool


class StructuredOutputError(Exception):
    """The model never produced a valid answer within the allowed attempts."""

    def __init__(self, attempts, last_error):
        super().__init__(f"no valid answer after {attempts} attempts: {last_error}")
        self.attempts = attempts
        self.last_error = last_error


_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def strip_fence(text: str) -> str:
    """Models often wrap JSON in a Markdown code fence. Remove exactly one fence, nothing else."""
    m = _FENCE.match(text.strip())
    return m.group(1) if m else text.strip()


def feedback(error: ValidationError) -> str:
    """Tell the model what was wrong: field path, error type, message. Never the input values."""
    lines = []
    for e in error.errors(include_input=False, include_url=False):
        where = ".".join(str(p) for p in e["loc"]) or "(root)"
        lines.append(f"- {where}: {e['msg']} [{e['type']}]")
    return "The JSON was not valid. Fix these problems and answer with the corrected JSON only:\n" + "\n".join(lines)


def extract(call_model: Callable[[list], str], prompt: str, model=Ticket, max_attempts: int = 3):
    """Ask the model, validate the answer, and on failure send the errors back.

    call_model(messages) -> str is your own wrapper around any provider.
    Returns (validated_object, attempts_used).
    """
    messages = [{"role": "user", "content": prompt}]
    last_error = None
    for attempt in range(1, max_attempts + 1):
        raw = call_model(messages)
        try:
            return model.model_validate_json(strip_fence(raw)), attempt
        except ValidationError as e:  # also covers invalid JSON (type "json_invalid")
            last_error = e
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": feedback(e)})
    raise StructuredOutputError(max_attempts, last_error)


def schema_for_provider(model=Ticket) -> str:
    """The JSON Schema you can pass to a provider feature that accepts one."""
    return json.dumps(model.model_json_schema(), indent=2)
