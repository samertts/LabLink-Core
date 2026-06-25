"""AI engine — manages providers and orchestrates analyses."""

from __future__ import annotations

import logging
import threading
from typing import Any

from app.ai.models import AIRequest, AIResponse, AnalysisType, ProviderConfig
from app.ai.provider import AIProvider
from app.ai.providers.local_mock import LocalMockProvider

logger = logging.getLogger("lablink.ai.engine")


class AIEngine:
    """Manages AI providers and routes analysis requests."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._providers: dict[str, AIProvider] = {}
        self._history: list[AIResponse] = []
        self._max_history = 500
        # Always register the local mock as fallback
        self._providers["local_mock"] = LocalMockProvider()
        self._default_provider = "local_mock"

    def register_provider(self, name: str, provider: AIProvider) -> None:
        with self._lock:
            self._providers[name] = provider
        logger.info("Registered AI provider: %s", name)

    def configure_openai(self, config: ProviderConfig) -> None:
        from app.ai.providers.openai_provider import OpenAIProvider
        provider = OpenAIProvider(config)
        self.register_provider("openai", provider)

    def set_default_provider(self, name: str) -> None:
        with self._lock:
            if name in self._providers:
                self._default_provider = name

    def get_provider(self, name: str | None = None) -> AIProvider | None:
        with self._lock:
            return self._providers.get(name or self._default_provider)

    def list_providers(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "name": name,
                    "type": p.provider_name,
                    "capabilities": p.capabilities(),
                    "healthy": p.health_check(),
                }
                for name, p in self._providers.items()
            ]

    def analyze(self, request: AIRequest, provider_name: str | None = None) -> AIResponse:
        provider = self.get_provider(provider_name)
        if provider is None:
            return AIResponse(
                analysis_type=request.analysis_type,
                result={},
                error=f"Provider '{provider_name}' not found",
            )
        response = provider.analyze(request)
        with self._lock:
            self._history.append(response)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        return response

    def analyze_logs(self, logs: list[dict[str, Any]], **kwargs: Any) -> AIResponse:
        return self.analyze(AIRequest(
            analysis_type=AnalysisType.LOG_ANALYSIS,
            input_data={"logs": logs},
            **kwargs,
        ))

    def detect_anomalies(self, values: list[float], **kwargs: Any) -> AIResponse:
        return self.analyze(AIRequest(
            analysis_type=AnalysisType.ANOMALY_DETECTION,
            input_data={"values": values},
            **kwargs,
        ))

    def predict_failure(self, device_history: dict[str, Any], **kwargs: Any) -> AIResponse:
        return self.analyze(AIRequest(
            analysis_type=AnalysisType.FAILURE_PREDICTION,
            input_data={"device_history": device_history},
            **kwargs,
        ))

    def recognize_patterns(self, data_points: list[float], **kwargs: Any) -> AIResponse:
        return self.analyze(AIRequest(
            analysis_type=AnalysisType.PATTERN_RECOGNITION,
            input_data={"data_points": data_points},
            **kwargs,
        ))

    def root_cause_analysis(self, symptoms: list[str], **kwargs: Any) -> AIResponse:
        return self.analyze(AIRequest(
            analysis_type=AnalysisType.ROOT_CAUSE,
            input_data={"symptoms": symptoms},
            **kwargs,
        ))

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return [r.to_dict() for r in self._history[-limit:]]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._history)
            errors = sum(1 for r in self._history if r.error)
            providers = len(self._providers)
        return {
            "total_analyses": total,
            "errors": errors,
            "providers": providers,
            "default_provider": self._default_provider,
        }
