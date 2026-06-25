"""Tests for AI Integration Layer — providers, engine, analysis (Phase 10)."""

from __future__ import annotations

from app.ai.engine import AIEngine
from app.ai.models import AIProviderType, AIRequest, AIResponse, AnalysisType, ProviderConfig
from app.ai.providers.local_mock import LocalMockProvider

# ── LocalMockProvider Tests ────────────────────────────────────────


class TestLocalMockProvider:
    def test_provider_name(self) -> None:
        p = LocalMockProvider()
        assert p.provider_name == "local_mock"

    def test_capabilities(self) -> None:
        p = LocalMockProvider()
        caps = p.capabilities()
        assert len(caps) == 5
        assert "log_analysis" in caps

    def test_health_check(self) -> None:
        assert LocalMockProvider().health_check() is True

    def test_analyze_logs(self) -> None:
        p = LocalMockProvider()
        req = AIRequest(
            analysis_type=AnalysisType.LOG_ANALYSIS,
            input_data={"logs": [
                {"level": "ERROR", "message": "timeout"},
                {"level": "WARNING", "message": "slow"},
                {"level": "INFO", "message": "ok"},
            ]},
        )
        resp = p.analyze(req)
        assert resp.analysis_type == AnalysisType.LOG_ANALYSIS
        assert resp.result["error_count"] == 1
        assert resp.result["warning_count"] == 1
        assert resp.provider == "local_mock"

    def test_analyze_logs_empty(self) -> None:
        p = LocalMockProvider()
        req = AIRequest(analysis_type=AnalysisType.LOG_ANALYSIS, input_data={"logs": []})
        resp = p.analyze(req)
        assert resp.result["error_count"] == 0

    def test_detect_anomalies(self) -> None:
        p = LocalMockProvider()
        req = AIRequest(
            analysis_type=AnalysisType.ANOMALY_DETECTION,
            input_data={"values": [1.0, 1.1, 1.0, 1.2, 50.0]},
        )
        resp = p.analyze(req)
        assert resp.analysis_type == AnalysisType.ANOMALY_DETECTION
        assert "anomalies" in resp.result

    def test_detect_anomalies_empty(self) -> None:
        p = LocalMockProvider()
        req = AIRequest(analysis_type=AnalysisType.ANOMALY_DETECTION, input_data={"values": []})
        resp = p.analyze(req)
        assert resp.result["anomaly_count"] == 0
        assert resp.result["anomalies"] == []

    def test_predict_failures(self) -> None:
        p = LocalMockProvider()
        req = AIRequest(
            analysis_type=AnalysisType.FAILURE_PREDICTION,
            input_data={"device_history": {"consecutive_errors": 5, "uptime_hours": 1000, "last_maintenance_days": 120}},
        )
        resp = p.analyze(req)
        assert resp.result["risk_level"] == "high"
        assert resp.result["risk_score"] > 0.5

    def test_predict_failures_low_risk(self) -> None:
        p = LocalMockProvider()
        req = AIRequest(
            analysis_type=AnalysisType.FAILURE_PREDICTION,
            input_data={"device_history": {"consecutive_errors": 0, "uptime_hours": 100, "last_maintenance_days": 10}},
        )
        resp = p.analyze(req)
        assert resp.result["risk_level"] == "low"

    def test_recognize_patterns(self) -> None:
        p = LocalMockProvider()
        req = AIRequest(
            analysis_type=AnalysisType.PATTERN_RECOGNITION,
            input_data={"data_points": [1.0, 2.0, 3.0, 4.0, 5.0]},
        )
        resp = p.analyze(req)
        assert resp.result["trend"] == "rising"

    def test_root_cause(self) -> None:
        p = LocalMockProvider()
        req = AIRequest(
            analysis_type=AnalysisType.ROOT_CAUSE,
            input_data={"symptoms": ["timeout on port 4000", "connection refused"]},
        )
        resp = p.analyze(req)
        assert len(resp.result["possible_causes"]) >= 1


# ── AIEngine Tests ─────────────────────────────────────────────────


class TestAIEngine:
    def test_default_provider(self) -> None:
        engine = AIEngine()
        assert engine.get_provider() is not None
        assert engine.get_provider().provider_name == "local_mock"

    def test_list_providers(self) -> None:
        engine = AIEngine()
        providers = engine.list_providers()
        assert len(providers) == 1
        assert providers[0]["name"] == "local_mock"
        assert providers[0]["healthy"] is True

    def test_analyze(self) -> None:
        engine = AIEngine()
        req = AIRequest(analysis_type=AnalysisType.LOG_ANALYSIS, input_data={"logs": []})
        resp = engine.analyze(req)
        assert resp.error is None
        assert resp.provider == "local_mock"

    def test_analyze_unknown_provider(self) -> None:
        engine = AIEngine()
        req = AIRequest(analysis_type=AnalysisType.LOG_ANALYSIS, input_data={"logs": []})
        resp = engine.analyze(req, provider_name="nonexistent")
        assert resp.error is not None

    def test_convenience_methods(self) -> None:
        engine = AIEngine()
        r1 = engine.analyze_logs([{"level": "ERROR", "message": "fail"}])
        assert r1.result["error_count"] == 1

        r2 = engine.detect_anomalies([1.0, 2.0, 50.0])
        assert "anomalies" in r2.result

        r3 = engine.predict_failure({"consecutive_errors": 5, "uptime_hours": 800, "last_maintenance_days": 100})
        assert r3.result["risk_level"] == "high"

        r4 = engine.recognize_patterns([1.0, 2.0, 3.0])
        assert r4.result["trend"] == "rising"

        r5 = engine.root_cause_analysis(["timeout error"])
        assert len(r5.result["possible_causes"]) >= 1

    def test_history(self) -> None:
        engine = AIEngine()
        engine.analyze(AIRequest(analysis_type=AnalysisType.LOG_ANALYSIS, input_data={"logs": []}))
        engine.analyze(AIRequest(analysis_type=AnalysisType.ANOMALY_DETECTION, input_data={"values": []}))
        history = engine.get_history()
        assert len(history) == 2

    def test_summary(self) -> None:
        engine = AIEngine()
        engine.analyze(AIRequest(analysis_type=AnalysisType.LOG_ANALYSIS, input_data={"logs": []}))
        s = engine.summary()
        assert s["total_analyses"] == 1
        assert s["errors"] == 0
        assert s["providers"] == 1

    def test_set_default_provider(self) -> None:
        engine = AIEngine()
        engine.set_default_provider("local_mock")
        assert engine._default_provider == "local_mock"


# ── Model Tests ────────────────────────────────────────────────────


class TestModels:
    def test_ai_response_to_dict(self) -> None:
        r = AIResponse(
            analysis_type=AnalysisType.LOG_ANALYSIS,
            result={"summary": "test"},
            confidence=0.9,
            provider="test",
            model="m1",
            tokens_used=100,
            duration_ms=50.0,
        )
        d = r.to_dict()
        assert d["analysis_type"] == "log_analysis"
        assert d["confidence"] == 0.9
        assert d["tokens_used"] == 100

    def test_provider_config(self) -> None:
        cfg = ProviderConfig(provider_type=AIProviderType.OPENAI, api_key="sk-test")
        assert cfg.provider_type == AIProviderType.OPENAI
        assert cfg.api_key == "sk-test"
