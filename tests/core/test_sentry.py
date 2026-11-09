"""Sentry is optional: no DSN must mean no init at all."""

import sentry_sdk

from app.config import settings
from app.main import configure_sentry


def test_no_dsn_means_sentry_never_starts(monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "SENTRY_DSN", "")
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: calls.append(kw))
    configure_sentry()
    assert calls == []


def test_dsn_starts_sentry_without_pii(monkeypatch):
    calls = []
    monkeypatch.setattr(settings, "SENTRY_DSN", "https://key@o0.ingest.sentry.io/0")
    monkeypatch.setattr(sentry_sdk, "init", lambda **kw: calls.append(kw))
    configure_sentry()
    assert calls[0]["dsn"] == "https://key@o0.ingest.sentry.io/0"
    assert calls[0]["send_default_pii"] is False
