from __future__ import annotations

from pathlib import Path

from app.config.settings import AppSettings, get_settings


class TestAppSettings:
    def test_defaults(self) -> None:
        settings = AppSettings()
        assert settings.app_name == "LabLink Core"
        assert settings.version == "1.3.0"
        assert settings.environment == "development"
        assert settings.port == 8000
        assert settings.debug is False

    def test_effective_db_path_default(self) -> None:
        settings = AppSettings()
        assert settings.effective_db_path.endswith("lablink.db")

    def test_effective_db_path_custom(self) -> None:
        settings = AppSettings(db_path="/tmp/custom.db")
        assert settings.effective_db_path == "/tmp/custom.db"

    def test_is_production(self) -> None:
        settings = AppSettings(environment="production")
        assert settings.is_production is True
        dev_settings = AppSettings(environment="development")
        assert dev_settings.is_production is False

    def test_cors_origins_default(self) -> None:
        settings = AppSettings()
        assert "http://127.0.0.1:8000" in settings.cors_origins

    def test_data_dir_created(self, tmp_path: Path) -> None:
        test_dir = tmp_path / "test_data"
        AppSettings(data_dir=str(test_dir))
        assert test_dir.exists()

    def test_env_override(self, monkeypatch) -> None:
        monkeypatch.setenv("LABLINK_PORT", "9999")
        settings = AppSettings()
        assert settings.port == 9999

    def test_worker_defaults(self) -> None:
        settings = AppSettings()
        assert settings.worker_enabled is True
        assert settings.worker_max_retries == 3


class TestGetSettings:
    def test_singleton(self) -> None:
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2
