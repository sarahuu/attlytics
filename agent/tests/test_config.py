import importlib
import sys
from pathlib import Path

import agent.config as config_module


def test_config_reflects_env_overrides(monkeypatch):
    # Set every config key so the repo .env cannot interfere with the test.
    monkeypatch.setenv("DB_PATH", "custom/path.db")
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "5")
    monkeypatch.setenv("HEARTBEAT_INTERVAL_SECONDS", "10")
    monkeypatch.setenv("IDLE_THRESHOLD_SECONDS", "30")

    importlib.reload(config_module)

    assert config_module.DB_PATH == Path("custom/path.db")
    assert config_module.POLL_INTERVAL_SECONDS == 5.0
    assert config_module.HEARTBEAT_INTERVAL_SECONDS == 10.0
    assert config_module.IDLE_THRESHOLD_SECONDS == 30.0


def test_db_path_defaults_under_agent_data():
    assert config_module.DEFAULT_DB_PATH.parent.name == "data"
    assert config_module.DEFAULT_DB_PATH.name == "activity_events.db"


def test_config_frozen_uses_home_data_dir(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    importlib.reload(config_module)

    assert config_module.DEFAULT_DB_PATH == (
        Path.home() / ".attlytics" / "data" / "activity_events.db"
    )
