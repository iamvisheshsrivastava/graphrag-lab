"""
Tests for backend/security.py — the optional API-key dependency and the
in-memory per-IP rate limiter added for issue #2.
"""
from collections import defaultdict

import pytest
from fastapi import HTTPException

import security


def _fresh_buckets():
    return defaultdict(lambda: (0.0, 0))


def test_require_api_key_is_noop_when_unset(monkeypatch):
    monkeypatch.setattr(security, "API_KEY", None)
    # No header, no key configured -> passes silently.
    security.require_api_key(x_api_key=None)


def test_require_api_key_rejects_missing_header_when_set(monkeypatch):
    monkeypatch.setattr(security, "API_KEY", "secret123")
    with pytest.raises(HTTPException) as exc_info:
        security.require_api_key(x_api_key=None)
    assert exc_info.value.status_code == 401


def test_require_api_key_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(security, "API_KEY", "secret123")
    with pytest.raises(HTTPException) as exc_info:
        security.require_api_key(x_api_key="wrong")
    assert exc_info.value.status_code == 401


def test_require_api_key_accepts_matching_key(monkeypatch):
    monkeypatch.setattr(security, "API_KEY", "secret123")
    # Should not raise.
    security.require_api_key(x_api_key="secret123")


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, ip, forwarded_for=None):
        self.client = _FakeClient(ip)
        self.headers = {"x-forwarded-for": forwarded_for} if forwarded_for else {}


def test_rate_limit_allows_requests_under_the_cap(monkeypatch):
    monkeypatch.setattr(security, "_buckets", _fresh_buckets())
    monkeypatch.setattr(security, "RATE_LIMIT_MAX_REQUESTS", 3)
    monkeypatch.setattr(security, "RATE_LIMIT_WINDOW_SECONDS", 60)
    req = _FakeRequest("1.2.3.4")
    for _ in range(3):
        security.rate_limit_llm(req)  # should not raise


def test_rate_limit_blocks_after_cap_exceeded(monkeypatch):
    monkeypatch.setattr(security, "_buckets", _fresh_buckets())
    monkeypatch.setattr(security, "RATE_LIMIT_MAX_REQUESTS", 2)
    monkeypatch.setattr(security, "RATE_LIMIT_WINDOW_SECONDS", 60)
    req = _FakeRequest("5.6.7.8")
    security.rate_limit_llm(req)
    security.rate_limit_llm(req)
    with pytest.raises(HTTPException) as exc_info:
        security.rate_limit_llm(req)
    assert exc_info.value.status_code == 429


def test_rate_limit_resets_after_window_elapses(monkeypatch):
    monkeypatch.setattr(security, "_buckets", _fresh_buckets())
    monkeypatch.setattr(security, "RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr(security, "RATE_LIMIT_WINDOW_SECONDS", 60)
    req = _FakeRequest("9.9.9.9")
    security.rate_limit_llm(req)
    with pytest.raises(HTTPException):
        security.rate_limit_llm(req)

    # Simulate the window elapsing by rewinding the stored window start.
    ip = "9.9.9.9"
    window_start, count = security._buckets[ip]
    security._buckets[ip] = (window_start - 61, count)

    security.rate_limit_llm(req)  # should not raise — new window


def test_rate_limit_tracks_ips_independently(monkeypatch):
    monkeypatch.setattr(security, "_buckets", _fresh_buckets())
    monkeypatch.setattr(security, "RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr(security, "RATE_LIMIT_WINDOW_SECONDS", 60)
    req_a = _FakeRequest("1.1.1.1")
    req_b = _FakeRequest("2.2.2.2")
    security.rate_limit_llm(req_a)
    security.rate_limit_llm(req_b)  # different IP, should not raise
    with pytest.raises(HTTPException):
        security.rate_limit_llm(req_a)


def test_client_ip_prefers_x_forwarded_for():
    req = _FakeRequest("10.0.0.1", forwarded_for="203.0.113.5, 10.0.0.1")
    assert security._client_ip(req) == "203.0.113.5"


def test_stale_buckets_are_evicted_after_cleanup_interval(monkeypatch):
    """Issue #18: _buckets must not grow unboundedly — stale entries whose
    window has long expired should be swept out once the cleanup interval
    has elapsed."""
    monkeypatch.setattr(security, "_buckets", _fresh_buckets())
    monkeypatch.setattr(security, "_last_cleanup", 0.0)
    monkeypatch.setattr(security, "RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(security, "_CLEANUP_INTERVAL_SECONDS", 300)

    old_ip = "1.2.3.4"
    security._buckets[old_ip] = (0.0, 1)  # long-expired window

    # Cleanup interval hasn't elapsed since _last_cleanup (0.0) yet -> no sweep.
    security._evict_stale_buckets(10.0)
    assert old_ip in security._buckets

    # Interval has now elapsed, and the bucket's window is well past
    # RATE_LIMIT_WINDOW_SECONDS -> it gets swept.
    security._evict_stale_buckets(301.0)
    assert old_ip not in security._buckets


def test_fresh_buckets_survive_cleanup(monkeypatch):
    monkeypatch.setattr(security, "_buckets", _fresh_buckets())
    monkeypatch.setattr(security, "_last_cleanup", 0.0)
    monkeypatch.setattr(security, "RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(security, "_CLEANUP_INTERVAL_SECONDS", 300)

    fresh_ip = "9.1.1.1"
    security._buckets[fresh_ip] = (300.0, 1)  # window just started

    # Cleanup interval has elapsed, but this bucket's window is still
    # within RATE_LIMIT_WINDOW_SECONDS of "now" -> it survives.
    security._evict_stale_buckets(301.0)
    assert fresh_ip in security._buckets
