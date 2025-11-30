"""c7n_azure_container_apps.cli のユニットテスト"""

import os

import click
import pytest

import c7n_azure_container_apps.cli as cli


class _SessionStub:
    def __init__(self, subscription_id=None):
        self.subscription_id = subscription_id


def test_prepare_subscription_session_primes_cache(monkeypatch):
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "original")

    calls: dict[str, int | str] = {}

    def _fake_reset():
        calls["reset"] = calls.get("reset", 0) + 1

    def _fake_local_session(factory):
        calls["local_session"] = calls.get("local_session", 0) + 1
        instance = factory()
        calls["subscription"] = instance.subscription_id
        return instance

    monkeypatch.setattr(cli, "reset_session_cache", _fake_reset)
    monkeypatch.setattr(cli, "local_session", _fake_local_session)
    monkeypatch.setattr(cli, "Session", _SessionStub)

    cli._prepare_subscription_session("  sub-override  ")

    assert os.environ["AZURE_SUBSCRIPTION_ID"] == "sub-override"
    assert calls["reset"] == 1
    assert calls["local_session"] == 1
    assert calls["subscription"] == "sub-override"


def test_prepare_subscription_session_rejects_blank(monkeypatch):
    def _fail(*_args, **_kwargs):  # pragma: no cover - should never be called
        raise AssertionError("Should not be invoked for blank subscription")

    monkeypatch.setattr(cli, "reset_session_cache", _fail)
    monkeypatch.setattr(cli, "local_session", _fail)
    monkeypatch.setattr(cli, "Session", _SessionStub)

    with pytest.raises(click.BadParameter):
        cli._prepare_subscription_session("   ")
