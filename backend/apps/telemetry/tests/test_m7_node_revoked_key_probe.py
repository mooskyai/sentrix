"""Negative credential smoke semantics without real credentials or network calls."""

from __future__ import annotations

from email.message import Message
from urllib.error import HTTPError, URLError

import pytest

from scripts import m7_node_revoked_key_probe as probe


class FakeResponse:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_returns_true_only_for_http_401(monkeypatch: pytest.MonkeyPatch) -> None:
    def unauthorized(*_args: object, **_kwargs: object) -> FakeResponse:
        raise HTTPError(probe.OTLP_TRACES_URL, 401, "Unauthorized", Message(), None)

    monkeypatch.setattr(probe, "urlopen", unauthorized)
    assert probe.check_revoked_key("fake-test-key")
    monkeypatch.setattr(probe, "urlopen", lambda *_args, **_kw: FakeResponse(200))
    assert not probe.check_revoked_key("fake-test-key")


def test_network_error_does_not_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    def offline(*_args: object, **_kwargs: object) -> None:
        raise URLError("unreachable")

    monkeypatch.setattr(probe, "urlopen", offline)
    assert not probe.check_revoked_key("fake-test-key")
    assert not probe.check_revoked_key("")
