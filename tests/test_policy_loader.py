"""policy_loader のユニットテスト"""

from types import SimpleNamespace

import pytest

from c7n_azure_runner.policy_loader import PolicyLoader


class _DummyClient:
    def __init__(self, blob_names):
        self._blob_names = blob_names
        self.calls = []

    def list_blobs(self, container):
        self.calls.append((container,))
        return [SimpleNamespace(name=name) for name in self._blob_names]


def _make_loader_without_init() -> PolicyLoader:
    # __init__ は Azure リソース初期化を行うため、テストでは回避する
    return PolicyLoader.__new__(PolicyLoader)


def test_iter_policy_blobs_filters_by_prefix_and_extension():
    loader = _make_loader_without_init()
    client = _DummyClient(
        [
            "foo/a.yaml",
            "foo/b.yml",
            "foo/c.txt",
            "bar/d.yaml",
        ]
    )

    blobs = list(loader._iter_policy_blobs(client, "container", "foo/"))

    assert [b.name for b in blobs] == ["foo/a.yaml", "foo/b.yml"]
    assert client.calls == [("container",)]


def test_iter_policy_blobs_allows_empty_prefix():
    loader = _make_loader_without_init()
    client = _DummyClient(["a.yaml", "b.yml", "c.txt"])

    blobs = list(loader._iter_policy_blobs(client, "container", ""))

    assert [b.name for b in blobs] == ["a.yaml", "b.yml"]
    assert client.calls == [("container",)]


def test_read_blob_content_supports_bytes():
    data = b"foo"

    assert PolicyLoader._read_blob_content(data) == b"foo"


def test_read_blob_content_supports_content_attr():
    class _Response:
        content = b"bar"

    assert PolicyLoader._read_blob_content(_Response()) == b"bar"


def test_read_blob_content_supports_readall():
    class _Stream:
        def readall(self):
            return b"baz"

    assert PolicyLoader._read_blob_content(_Stream()) == b"baz"


def test_load_from_blob_passes_subscription_override(monkeypatch):
    loader = _make_loader_without_init()
    monkeypatch.setenv("AZURE_SUBSCRIPTION_ID", "sub-override")

    captured = {}

    class _DummySession:
        def __init__(self, subscription_id=None):
            captured["subscription_id"] = subscription_id

    def _fake_local_session(factory):
        captured["factory_type"] = type(factory)
        return factory()

    class _DummyStorage:
        @staticmethod
        def get_blob_client_by_uri(blob_uri, session):  # noqa: ARG004
            raise RuntimeError("stop-after-session")

    monkeypatch.setattr("c7n_azure_runner.policy_loader.Session", _DummySession)
    monkeypatch.setattr("c7n_azure_runner.policy_loader.local_session", _fake_local_session)
    monkeypatch.setattr("c7n_azure_runner.policy_loader.Storage", _DummyStorage)

    with pytest.raises(RuntimeError, match="stop-after-session"):
        loader.load_from_blob("https://example", session=None)

    assert captured["subscription_id"] == "sub-override"
