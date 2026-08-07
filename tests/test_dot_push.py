"""dot_push._post 的重试退避与错误分支测试."""

from __future__ import annotations

import io
import urllib.error

import pytest

from worker_reminder import dot_push


class _FakeResp:
    def __init__(self, status: int, body: bytes) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *args) -> None:
        return None


def _http_error(url: str, status: int, body: bytes) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, status, "err", {}, io.BytesIO(body))


def test_post_retries_5xx_then_success(monkeypatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(dot_push.time, "sleep", lambda s: None)

    def fake_urlopen(req, timeout=0, context=None):
        calls.append(1)
        if len(calls) < 3:
            raise _http_error(req.full_url, 503, b'{"message":"server busy"}')
        return _FakeResp(200, b'{"message":"ok"}')

    monkeypatch.setattr("worker_reminder.dot_push.urllib.request.urlopen", fake_urlopen)
    assert dot_push._post("http://x/1", "k", {}, "test") == "ok"
    assert len(calls) == 3


def test_post_5xx_exhausted_raises(monkeypatch) -> None:
    monkeypatch.setattr(dot_push.time, "sleep", lambda s: None)

    def fake_urlopen(req, timeout=0, context=None):
        raise _http_error(req.full_url, 500, b'{"message":"boom"}')

    monkeypatch.setattr("worker_reminder.dot_push.urllib.request.urlopen", fake_urlopen)
    with pytest.raises(dot_push.DotPushError, match="500"):
        dot_push._post("http://x/1", "k", {}, "test")


def test_post_network_error_exhausted_raises(monkeypatch) -> None:
    monkeypatch.setattr(dot_push.time, "sleep", lambda s: None)

    def fake_urlopen(req, timeout=0, context=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("worker_reminder.dot_push.urllib.request.urlopen", fake_urlopen)
    with pytest.raises(dot_push.DotPushError, match="Network error"):
        dot_push._post("http://x/1", "k", {}, "test")


@pytest.mark.parametrize("status,exc", [
    (400, dot_push.DotValidationError),
    (401, dot_push.DotAuthError),
    (403, dot_push.DotAuthError),
    (404, dot_push.DotDeviceNotFoundError),
])
def test_post_client_errors_raise_without_retry(monkeypatch, status, exc) -> None:
    calls: list[int] = []

    def fake_urlopen(req, timeout=0, context=None):
        calls.append(1)
        raise _http_error(req.full_url, status, b'{"message":"client err"}')

    monkeypatch.setattr("worker_reminder.dot_push.urllib.request.urlopen", fake_urlopen)
    with pytest.raises(exc):
        dot_push._post("http://x/1", "k", {}, "test")
    assert len(calls) == 1  # 客户端错误不重试


def test_post_success_message_extraction(monkeypatch) -> None:
    monkeypatch.setattr("worker_reminder.dot_push.urllib.request.urlopen",
                        lambda *a, **k: _FakeResp(200, b'{"message":"pushed"}'))
    assert dot_push._post("http://x/1", "k", {}, "test") == "pushed"


def test_device_id_hint() -> None:
    assert dot_push.device_id_hint("http://x/1/dev-123/canvas") == "dev-123"
