from __future__ import annotations

import pytest

from app.services import notifier


class FakeEmailResponse:
    status_code = 201
    text = '{"messageId":"test"}'


class FakeAsyncClient:
    posted = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, headers=None, json=None):
        self.posted.append((url, headers or {}, json or {}))
        return FakeEmailResponse()


def test_auto_provider_prefers_brevo_when_configured(monkeypatch):
    monkeypatch.setattr(notifier.settings, "email_delivery_provider", "auto")
    monkeypatch.setattr(notifier.settings, "brevo_api_key", "brevo-key")
    monkeypatch.setattr(notifier.settings, "brevo_from_email", "alerts@example.com")
    monkeypatch.setattr(notifier.settings, "resend_api_key", "resend-key")

    assert notifier._email_delivery_provider() == "brevo"


def test_auto_provider_falls_back_to_resend_for_existing_deployments(monkeypatch):
    monkeypatch.setattr(notifier.settings, "email_delivery_provider", "auto")
    monkeypatch.setattr(notifier.settings, "brevo_api_key", "")
    monkeypatch.setattr(notifier.settings, "brevo_from_email", "")
    monkeypatch.setattr(notifier.settings, "resend_api_key", "resend-key")

    assert notifier._email_delivery_provider() == "resend"


@pytest.mark.asyncio
async def test_send_email_via_brevo_uses_transactional_api(monkeypatch):
    FakeAsyncClient.posted = []
    monkeypatch.setattr(notifier.settings, "email_delivery_provider", "brevo")
    monkeypatch.setattr(notifier.settings, "brevo_api_key", "brevo-key")
    monkeypatch.setattr(notifier.settings, "brevo_from_email", "alerts@example.com")
    monkeypatch.setattr(notifier.settings, "brevo_from_name", "NafaIQ Alerts")
    monkeypatch.setattr(notifier.httpx, "AsyncClient", FakeAsyncClient)

    ok = await notifier.send_email("user@example.com", "Bill due", "<p>Pay today</p>")

    assert ok is True
    assert FakeAsyncClient.posted == [
        (
            "https://api.brevo.com/v3/smtp/email",
            {
                "accept": "application/json",
                "api-key": "brevo-key",
                "content-type": "application/json",
            },
            {
                "sender": {"name": "NafaIQ Alerts", "email": "alerts@example.com"},
                "to": [{"email": "user@example.com"}],
                "subject": "Bill due",
                "htmlContent": "<p>Pay today</p>",
            },
        )
    ]


@pytest.mark.asyncio
async def test_send_email_via_resend_keeps_existing_http_contract(monkeypatch):
    FakeAsyncClient.posted = []
    FakeEmailResponse.status_code = 200
    monkeypatch.setattr(notifier.settings, "email_delivery_provider", "resend")
    monkeypatch.setattr(notifier.settings, "resend_api_key", "resend-key")
    monkeypatch.setattr(notifier.settings, "resend_from_email", "alerts@nafaiq.app")
    monkeypatch.setattr(notifier.httpx, "AsyncClient", FakeAsyncClient)

    ok = await notifier.send_email("user@example.com", "Alert", "<p>Hello</p>")

    assert ok is True
    assert FakeAsyncClient.posted == [
        (
            "https://api.resend.com/emails",
            {
                "Authorization": "Bearer resend-key",
                "Content-Type": "application/json",
            },
            {
                "from": "alerts@nafaiq.app",
                "to": ["user@example.com"],
                "subject": "Alert",
                "html": "<p>Hello</p>",
            },
        )
    ]
