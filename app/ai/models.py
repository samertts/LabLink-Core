"""AI Integration Layer — models and provider interface."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class AIProviderType(str, enum.Enum):
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    LOCAL_MOCK = "local_mock"
    CUSTOM = "custom"


class AnalysisType(str, enum.Enum):
    LOG_ANALYSIS = "log_analysis"
    ANOMALY_DETECTION = "anomaly_detection"
    FAILURE_PREDICTION = "failure_prediction"
    PATTERN_RECOGNITION = "pattern_recommendation"
    ROOT_CAUSE = "root_cause_analysis"


@dataclass
class AIRequest:
    analysis_type: AnalysisType
    input_data: dict[str, Any]
    context: dict[str, Any] = field(default_factory=dict)
    model_hint: str = ""
    max_tokens: int = 1024
    temperature: float = 0.3


@dataclass
class AIResponse:
    analysis_type: AnalysisType
    result: dict[str, Any]
    confidence: float = 0.0
    provider: str = ""
    model: str = ""
    tokens_used: int = 0
    duration_ms: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_type": self.analysis_type.value,
            "result": self.result,
            "confidence": self.confidence,
            "provider": self.provider,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "duration_ms": round(self.duration_ms, 2),
            "error": self.error,
        }


@dataclass
class ProviderConfig:
    provider_type: AIProviderType = AIProviderType.LOCAL_MOCK
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    timeout_seconds: float = 30.0
    max_retries: int = 2
    extra: dict[str, Any] = field(default_factory=dict)
