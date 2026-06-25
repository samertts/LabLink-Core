"""Abstract AI provider interface."""

from __future__ import annotations

import abc

from app.ai.models import AIRequest, AIResponse


class AIProvider(abc.ABC):
    """Abstract base class for AI providers.

    Implementations must define ``analyze()``.  The core never embeds a
    model — it always delegates to an external provider via this interface.
    """

    @abc.abstractmethod
    def analyze(self, request: AIRequest) -> AIResponse:
        """Run an analysis request and return a response."""

    @abc.abstractmethod
    def health_check(self) -> bool:
        """Return True if the provider is reachable and configured."""

    @abc.abstractmethod
    def capabilities(self) -> list[str]:
        """Return list of supported analysis types."""

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
