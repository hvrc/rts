"""Provider registry — the one place that decides which brain answers.

Add a model backend by writing a Provider subclass and adding a line to _REGISTRY.
Callers only ever see get_provider().
"""

from .. import config
from .anthropic_provider import AnthropicProvider
from .base import Provider, TurnContext
from .openai_provider import OpenAIProvider
from .stub_provider import StubProvider

_REGISTRY = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "stub": StubProvider,
}

_cached = None


def get_provider():
    """The provider named by RTS_PROVIDER. Built once — the choice can't change
    without a restart, and constructing one is not free."""
    global _cached
    if _cached is None:
        try:
            cls = _REGISTRY[config.PROVIDER]
        except KeyError:
            raise ValueError(
                f"unknown RTS_PROVIDER={config.PROVIDER!r}; "
                f"expected one of {', '.join(sorted(_REGISTRY))}"
            )
        _cached = cls()
    return _cached


__all__ = ["Provider", "TurnContext", "get_provider"]
