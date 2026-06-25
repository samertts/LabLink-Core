"""OpenAI API provider — delegates to OpenAI/Azure OpenAI endpoints."""

from __future__ import annotations

import json
import logging
import time

from app.ai.models import AIRequest, AIResponse, AnalysisType, ProviderConfig
from app.ai.provider import AIProvider

logger = logging.getLogger("lablink.ai.openai")

_SYSTEM_PROMPTS = {
    AnalysisType.LOG_ANALYSIS: "You are a laboratory device log analyst. Analyze the provided logs and identify errors, warnings, and patterns. Return JSON with: summary, error_count, warning_count, top_errors, root_cause.",
    AnalysisType.ANOMALY_DETECTION: "You are a laboratory data anomaly detector. Analyze the provided values and identify anomalies using statistical methods. Return JSON with: anomalies, mean, std, threshold.",
    AnalysisType.FAILURE_PREDICTION: "You are a laboratory device failure predictor. Analyze device history and predict failure risk. Return JSON with: risk_score, risk_level, factors, recommendation.",
    AnalysisType.PATTERN_RECOGNITION: "You are a laboratory data pattern recognizer. Analyze data points and identify trends and patterns. Return JSON with: trend, patterns, confidence.",
    AnalysisType.ROOT_CAUSE: "You are a laboratory device root cause analyst. Analyze symptoms and identify possible causes. Return JSON with: possible_causes, top_cause, confidence.",
}


class OpenAIProvider(AIProvider):
    """OpenAI / Azure OpenAI provider using httpx for HTTP calls."""

    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._base_url = config.base_url or "https://api.openai.com/v1"
        self._model = config.model or "gpt-4o-mini"

    @property
    def provider_name(self) -> str:
        return "openai"

    def capabilities(self) -> list[str]:
        return [a.value for a in AnalysisType]

    def health_check(self) -> bool:
        if not self._config.api_key:
            return False
        try:
            import httpx
            resp = httpx.get(
                f"{self._base_url}/models",
                headers={"Authorization": f"Bearer {self._config.api_key}"},
                timeout=5.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def analyze(self, request: AIRequest) -> AIResponse:
        start = time.monotonic()
        try:
            import httpx
            system_prompt = _SYSTEM_PROMPTS.get(request.analysis_type, "Analyze the provided data.")
            user_content = json.dumps(request.input_data, default=str)

            payload = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
            }

            resp = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._config.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()

            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            duration = (time.monotonic() - start) * 1000

            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                result = {"raw_response": content}

            return AIResponse(
                analysis_type=request.analysis_type,
                result=result,
                confidence=result.get("confidence", 0.8),
                provider=self.provider_name,
                model=self._model,
                tokens_used=tokens,
                duration_ms=duration,
            )
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            logger.error("OpenAI analysis failed: %s", exc)
            return AIResponse(
                analysis_type=request.analysis_type,
                result={},
                provider=self.provider_name,
                model=self._model,
                duration_ms=duration,
                error=str(exc),
            )
