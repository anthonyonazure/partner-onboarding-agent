"""Optional Langfuse tracing.

Enabled when LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are set.
Otherwise the @traced decorator is a transparent no-op.

Why opt-in: keeps the demo runnable for anyone who clones the repo without
needing a Langfuse account, while production users get full LLM + agent
observability by setting two env vars.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any, Literal, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

# The observation kinds Langfuse's @observe accepts. Spelling it out here keeps
# the no-op branch and the real branch agreeing on one signature.
ObservationType = Literal[
    "generation",
    "embedding",
    "span",
    "agent",
    "tool",
    "chain",
    "retriever",
    "evaluator",
    "guardrail",
]


def _enabled() -> bool:
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY")
    )


if _enabled():
    from langfuse import observe  # type: ignore[import-not-found]

    def traced(
        name: str | None = None, as_type: ObservationType | None = None
    ) -> Callable[[F], F]:
        """Wrap an async function so each call becomes a Langfuse span.

        as_type='generation' marks LLM calls (gets token-cost UI in Langfuse).
        """

        def decorator(fn: F) -> F:
            return observe(name=name or fn.__name__, as_type=as_type)(fn)  # type: ignore[return-value]

        return decorator

    def flush() -> None:
        from langfuse import get_client

        get_client().flush()

else:

    def traced(
        name: str | None = None, as_type: ObservationType | None = None
    ) -> Callable[[F], F]:
        def decorator(fn: F) -> F:
            return fn

        return decorator

    def flush() -> None:
        return None
