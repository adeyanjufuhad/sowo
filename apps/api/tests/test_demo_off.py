"""Nothing demo-related runs unless it is asked for. Production is the default."""
import pytest
from fastapi.testclient import TestClient

from app import chat_cli, main, seed, seed_demo
from app.config import Settings, get_settings
from app.main import app


def _fresh_settings(monkeypatch: pytest.MonkeyPatch, **env: str) -> None:
    for name in ("ENVIRONMENT", "SIMULATOR_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()


def test_the_defaults_are_production_with_no_simulator() -> None:
    settings = Settings(_env_file=None)
    assert settings.environment == "production"
    assert settings.simulator_enabled is False


@pytest.mark.parametrize("command", [seed.main, seed_demo.main, chat_cli.main])
def test_demo_commands_refuse_to_run_in_production(command, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    _fresh_settings(monkeypatch)
    with pytest.raises(SystemExit) as stopped:
        command()
    assert "ENVIRONMENT=development" in str(stopped.value)


def test_a_bad_environment_value_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_simulator_endpoints_are_404_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    _fresh_settings(monkeypatch, DATABASE_URL=f"sqlite:///{tmp_path / 'off.db'}")
    with TestClient(app) as client:
        assert client.post("/simulator/messages", json={"body": "hi"}).status_code == 404
        assert client.post("/simulator/payments", json={"reference": "x", "outcome": "SUCCESS"}).status_code == 404
    get_settings.cache_clear()


def test_starting_with_the_simulator_on_in_production_warns(
    monkeypatch: pytest.MonkeyPatch, tmp_path, caplog: pytest.LogCaptureFixture
) -> None:
    _fresh_settings(monkeypatch, DATABASE_URL=f"sqlite:///{tmp_path / 'warn.db'}", SIMULATOR_ENABLED="true")
    monkeypatch.setattr(main, "settings", get_settings())
    with caplog.at_level("WARNING"), TestClient(app):
        pass
    assert "SIMULATOR_ENABLED is on in production" in caplog.text
    get_settings.cache_clear()
