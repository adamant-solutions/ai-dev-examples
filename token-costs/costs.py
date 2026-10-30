"""Count tokens and estimate the cost of a model call before you send it."""
from dataclasses import dataclass

import tiktoken


@dataclass(frozen=True)
class Price:
    """USD per million tokens (MTok)."""
    input: float
    output: float
    cache_write: float = 0.0  # 5-minute cache write
    cache_read: float = 0.0


# From https://platform.claude.com/docs/en/about-claude/pricing, checked 2026-10-30.
# Prices change: load them from configuration and re-check them, don't trust a copy in code.
PRICES = {
    "claude-sonnet-5-5": Price(input=2.00, output=10.00, cache_write=2.50, cache_read=0.10),
    "claude-opus-5-5": Price(input=4.00, output=20.00, cache_write=5.00, cache_read=0.20),
}


def count_tiktoken(text: str, encoding: str = "o200k_base") -> int:
    """Local count for OpenAI models (o200k_base: GPT-4o, GPT-4.1, GPT-5, o-series). Text only."""
    return len(tiktoken.get_encoding(encoding).encode(text))


def count_claude(client, model: str, messages: list, system: str | None = None) -> int:
    """Exact input count from Anthropic's free count_tokens endpoint (includes system prompt and tools)."""
    extra = {"system": system} if system else {}
    return client.messages.count_tokens(model=model, messages=messages, **extra).input_tokens


def count_openai(client, model: str, text: str) -> int:
    """Input count from OpenAI's POST /v1/responses/input_tokens endpoint."""
    return client.responses.input_tokens.count(model=model, input=text).input_tokens


def estimate_cost(input_tokens: int, max_output_tokens: int, price: Price) -> tuple[float, float]:
    """Cost range in USD: from an empty answer to an answer that uses all of max_output_tokens."""
    low = input_tokens * price.input / 1_000_000
    high = low + max_output_tokens * price.output / 1_000_000
    return low, high


def actual_cost(usage, price: Price) -> float:
    """Cost of a finished Claude call from response.usage (input_tokens excludes cached tokens)."""
    return (usage.input_tokens * price.input
            + (usage.cache_creation_input_tokens or 0) * price.cache_write
            + (usage.cache_read_input_tokens or 0) * price.cache_read
            + usage.output_tokens * price.output) / 1_000_000


class BudgetExceeded(Exception):
    pass


def check_budget(input_tokens: int, max_output_tokens: int, price: Price, max_usd: float) -> float:
    """Refuse a call whose worst case costs more than max_usd. Returns the worst case."""
    _, high = estimate_cost(input_tokens, max_output_tokens, price)
    if high > max_usd:
        raise BudgetExceeded(f"worst case ${high:.4f} is over the ${max_usd:.4f} limit")
    return high
