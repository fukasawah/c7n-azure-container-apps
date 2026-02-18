"""c7n_azure_container_apps.entrypoint のユニットテスト"""

import os

import c7n_azure_container_apps.entrypoint as entrypoint


def _clear_env(monkeypatch):
    for key in list(os.environ.keys()):
        monkeypatch.delenv(key, raising=False)


def test_detect_execution_mode_prefers_explicit(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("C7N_EXECUTION_MODE", "event")

    assert entrypoint.detect_execution_mode() == "event"


def test_detect_execution_mode_event_by_queue_legacy_vars(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("C7N_STORAGE_ACCOUNT", "storage")
    monkeypatch.setenv("C7N_QUEUE_NAME", "queue")

    assert entrypoint.detect_execution_mode() == "event"


def test_detect_execution_mode_event_by_queue_azure_vars(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("AZURE_QUEUE_STORAGE_ACCOUNT", "storage")
    monkeypatch.setenv("AZURE_QUEUE_NAME", "queue")

    assert entrypoint.detect_execution_mode() == "event"


def test_detect_execution_mode_single_by_policy_file(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("C7N_POLICY_FILE", "/path/to/policy.yml")

    assert entrypoint.detect_execution_mode() == "single"


def test_detect_execution_mode_defaults_to_scheduled(monkeypatch):
    _clear_env(monkeypatch)

    assert entrypoint.detect_execution_mode() == "scheduled"
