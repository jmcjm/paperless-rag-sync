import os

import pytest

from paperless_rag_sync.config import Config


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("PAPERLESS_URL", "http://paperless:8000")
    monkeypatch.setenv("PAPERLESS_API_TOKEN", "tok123")
    monkeypatch.setenv("OPENWEBUI_URL", "http://openwebui:8080")
    monkeypatch.setenv("OPENWEBUI_API_KEY", "sk-abc")
    monkeypatch.setenv("SYNC_INTERVAL_SECONDS", "30")
    monkeypatch.setenv("FULL_SCAN_EVERY_N_CYCLES", "5")

    cfg = Config.from_env()
    assert cfg.paperless_url == "http://paperless:8000"
    assert cfg.paperless_api_token == "tok123"
    assert cfg.openwebui_url == "http://openwebui:8080"
    assert cfg.openwebui_api_key == "sk-abc"
    assert cfg.sync_interval_seconds == 30
    assert cfg.full_scan_every_n_cycles == 5


def test_config_defaults(monkeypatch):
    monkeypatch.setenv("PAPERLESS_URL", "http://paperless:8000")
    monkeypatch.setenv("PAPERLESS_API_TOKEN", "tok123")
    monkeypatch.setenv("OPENWEBUI_URL", "http://openwebui:8080")
    monkeypatch.setenv("OPENWEBUI_API_KEY", "sk-abc")
    monkeypatch.delenv("SYNC_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("FULL_SCAN_EVERY_N_CYCLES", raising=False)

    cfg = Config.from_env()
    assert cfg.sync_interval_seconds == 60
    assert cfg.full_scan_every_n_cycles == 10


def test_config_missing_required(monkeypatch):
    monkeypatch.delenv("PAPERLESS_URL", raising=False)
    monkeypatch.delenv("PAPERLESS_API_TOKEN", raising=False)
    monkeypatch.delenv("OPENWEBUI_URL", raising=False)
    monkeypatch.delenv("OPENWEBUI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="PAPERLESS_URL"):
        Config.from_env()
