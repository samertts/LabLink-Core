"""Local mock AI provider — rule-based analysis for testing and fallback."""

from __future__ import annotations

import time
from typing import Any

from app.ai.models import AIRequest, AIResponse, AnalysisType
from app.ai.provider import AIProvider


class LocalMockProvider(AIProvider):
    """Rule-based mock provider that returns deterministic results without any external calls."""

    @property
    def provider_name(self) -> str:
        return "local_mock"

    def capabilities(self) -> list[str]:
        return [a.value for a in AnalysisType]

    def health_check(self) -> bool:
        return True

    def analyze(self, request: AIRequest) -> AIResponse:
        start = time.monotonic()
        handlers = {
            AnalysisType.LOG_ANALYSIS: self._analyze_logs,
            AnalysisType.ANOMALY_DETECTION: self._detect_anomalies,
            AnalysisType.FAILURE_PREDICTION: self._predict_failures,
            AnalysisType.PATTERN_RECOGNITION: self._recognize_patterns,
            AnalysisType.ROOT_CAUSE: self._root_cause,
        }
        handler = handlers.get(request.analysis_type, self._default_analysis)
        result = handler(request)
        duration = (time.monotonic() - start) * 1000
        return AIResponse(
            analysis_type=request.analysis_type,
            result=result,
            confidence=result.get("confidence", 0.85),
            provider=self.provider_name,
            model="rule_based_v1",
            tokens_used=0,
            duration_ms=duration,
        )

    def _analyze_logs(self, request: AIRequest) -> dict[str, Any]:
        logs = request.input_data.get("logs", [])
        errors = [entry for entry in logs if isinstance(entry, dict) and entry.get("level") == "ERROR"]
        warnings = [entry for entry in logs if isinstance(entry, dict) and entry.get("level") == "WARNING"]
        total = len(logs) if logs else 0
        return {
            "summary": f"Analyzed {total} log entries",
            "error_count": len(errors),
            "warning_count": len(warnings),
            "error_rate": len(errors) / max(total, 1),
            "top_errors": [e.get("message", "") for e in errors[:3]],
            "confidence": 0.85 if total > 0 else 0.0,
        }

    def _detect_anomalies(self, request: AIRequest) -> dict[str, Any]:
        values = request.input_data.get("values", [])
        if not values:
            return {"anomalies": [], "anomaly_count": 0, "confidence": 0.0}
        mean = sum(values) / len(values)
        std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5 if len(values) > 1 else 0
        threshold = mean + 2 * std if std > 0 else mean * 1.5
        anomalies = [{"value": v, "index": i} for i, v in enumerate(values) if v > threshold]
        return {
            "anomalies": anomalies,
            "anomaly_count": len(anomalies),
            "mean": round(mean, 3),
            "std": round(std, 3),
            "threshold": round(threshold, 3),
            "confidence": 0.80 if len(values) > 5 else 0.5,
        }

    def _predict_failures(self, request: AIRequest) -> dict[str, Any]:
        device_history = request.input_data.get("device_history", {})
        consecutive_errors = device_history.get("consecutive_errors", 0)
        uptime_hours = device_history.get("uptime_hours", 0)
        last_maintenance_days = device_history.get("last_maintenance_days", 0)

        risk_score = 0.0
        factors = []
        if consecutive_errors >= 3:
            risk_score += 0.3
            factors.append(f"consecutive_errors={consecutive_errors}")
        if uptime_hours > 720:
            risk_score += 0.2
            factors.append(f"uptime={uptime_hours}h")
        if last_maintenance_days > 90:
            risk_score += 0.2
            factors.append(f"maintenance_stale={last_maintenance_days}d")

        return {
            "risk_score": min(risk_score, 1.0),
            "risk_level": "high" if risk_score > 0.5 else "medium" if risk_score > 0.2 else "low",
            "factors": factors,
            "recommendation": "Schedule maintenance" if risk_score > 0.3 else "Continue monitoring",
            "confidence": 0.75,
        }

    def _recognize_patterns(self, request: AIRequest) -> dict[str, Any]:
        data_points = request.input_data.get("data_points", [])
        if not data_points:
            return {"patterns": [], "confidence": 0.0}
        # Simple pattern: check for rising/falling trends
        if len(data_points) >= 3:
            diffs = [data_points[i + 1] - data_points[i] for i in range(len(data_points) - 1)]
            avg_diff = sum(diffs) / len(diffs)
            trend = "rising" if avg_diff > 0.1 else "falling" if avg_diff < -0.1 else "stable"
        else:
            trend = "insufficient_data"
        return {
            "trend": trend,
            "data_points_analyzed": len(data_points),
            "confidence": 0.80 if len(data_points) >= 5 else 0.5,
        }

    def _root_cause(self, request: AIRequest) -> dict[str, Any]:
        symptoms = request.input_data.get("symptoms", [])
        possible_causes = []
        for symptom in symptoms:
            s = str(symptom).lower()
            if "timeout" in s:
                possible_causes.append({"cause": "Network latency or device overload", "likelihood": 0.7})
            elif "connection" in s or "connect" in s:
                possible_causes.append({"cause": "Physical connection issue", "likelihood": 0.8})
            elif "data" in s or "parse" in s:
                possible_causes.append({"cause": "Protocol mismatch or data corruption", "likelihood": 0.6})
            elif "permission" in s or "auth" in s:
                possible_causes.append({"cause": "Authentication credential issue", "likelihood": 0.9})
        if not possible_causes:
            possible_causes.append({"cause": "Insufficient information for diagnosis", "likelihood": 0.3})
        return {
            "possible_causes": possible_causes,
            "top_cause": possible_causes[0]["cause"] if possible_causes else "unknown",
            "confidence": max((c["likelihood"] for c in possible_causes), default=0.3),
        }

    def _default_analysis(self, request: AIRequest) -> dict[str, Any]:
        return {"message": "Analysis completed", "confidence": 0.5}
