"""Payment provider adapters (MTS §8 integration layer, §10). Business code talks only to this interface, so a
real provider (pending P-06) is one new adapter class plus its credentials, with no change elsewhere.

`sandbox` simulates a hosted-payment provider end to end: a hosted page, HMAC-signed callbacks, status checks
and refunds. It is enabled only where PAYMENTS_SANDBOX_ENABLED is true (local, CI, staging), never in production.
"""

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

from django.conf import settings
from django.utils import timezone


@dataclass
class StartResult:
    provider_ref: str
    redirect_url: str
    window_ends_at: datetime


@dataclass
class CheckResult:
    state: str  # succeeded | pending | failed | expired
    reason: str = ""


@dataclass
class RefundResult:
    ok: bool
    provider_ref: str = ""
    error: str = ""
    retryable: bool = True


@dataclass
class WebhookEvent:
    event_id: str
    kind: str  # payment.succeeded | payment.failed | payment.expired | payment.pending
    provider_ref: str
    data: dict[str, Any] = field(default_factory=dict)


class InvalidSignature(Exception):
    pass


class PaymentAdapter(Protocol):
    code: str
    label: str

    def start(self, payment_id: str, amount: Decimal, currency: str, return_url: str) -> StartResult: ...

    def check(self, provider_ref: str) -> CheckResult: ...

    def refund(self, provider_ref: str, amount: Decimal, idempotency_key: str) -> RefundResult: ...

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> list[WebhookEvent]: ...


def _sign(body: bytes) -> str:
    return hmac.new(settings.PAYMENTS_SANDBOX_SECRET.encode(), body, hashlib.sha256).hexdigest()


class SandboxAdapter:
    code = "sandbox"
    label = "Card (sandbox test payments)"
    WINDOW = timedelta(minutes=20)  # the simulated provider's own session timeout

    def start(self, payment_id: str, amount: Decimal, currency: str, return_url: str) -> StartResult:
        from apps.sandbox.models import SandboxPayment

        ref = "sbx_" + secrets.token_hex(10)
        SandboxPayment.objects.create(ref=ref, amount=amount, currency=currency, return_url=return_url)
        return StartResult(ref, f"{settings.SITE_URL}/api/v1/sandbox/pay/{ref}", timezone.now() + self.WINDOW)

    def check(self, provider_ref: str) -> CheckResult:
        from apps.sandbox.models import SandboxPayment

        sp = SandboxPayment.objects.filter(ref=provider_ref).first()
        if sp is None:
            return CheckResult("failed", "unknown payment")
        if sp.state == "pending" and timezone.now() > sp.created_at + self.WINDOW:
            sp.state = "expired"
            sp.save(update_fields=["state"])
        return CheckResult(sp.state)

    def refund(self, provider_ref: str, amount: Decimal, idempotency_key: str) -> RefundResult:
        from apps.sandbox.models import SandboxPayment

        sp = SandboxPayment.objects.select_for_update().filter(ref=provider_ref).first()
        if sp is None or sp.state != "succeeded":
            return RefundResult(False, error="payment not refundable", retryable=False)
        if amount > 0 and str(amount).endswith(".13"):  # test hook: amounts ending .13 fail, to exercise retries
            return RefundResult(False, error="sandbox refund declined")
        if sp.refunded + amount > sp.amount:
            return RefundResult(False, error="refund exceeds payment", retryable=False)
        sp.refunded += amount
        sp.save(update_fields=["refunded"])
        return RefundResult(True, provider_ref=f"rf_{idempotency_key[:20]}")

    def parse_webhook(self, body: bytes, headers: dict[str, str]) -> list[WebhookEvent]:
        supplied = headers.get("x-sandbox-signature", "")
        if not supplied or not hmac.compare_digest(supplied, _sign(body)):
            raise InvalidSignature("bad signature")
        data = json.loads(body)
        return [WebhookEvent(data["id"], data["type"], data["ref"], data)]

    # --- the provider's side (sandbox only) ---

    @staticmethod
    def signed_event(ref: str, kind: str) -> tuple[bytes, dict[str, str]]:
        body = json.dumps({"id": "evt_" + secrets.token_hex(8), "type": kind, "ref": ref}).encode()
        return body, {"x-sandbox-signature": _sign(body)}


def available() -> dict[str, PaymentAdapter]:
    adapters: dict[str, PaymentAdapter] = {}
    if settings.PAYMENTS_SANDBOX_ENABLED:
        adapters["sandbox"] = SandboxAdapter()
    # Real providers (P-06) register here once chosen, from credentials in the environment.
    return adapters


def get(code: str) -> PaymentAdapter | None:
    return available().get(code)


def online_adapter() -> PaymentAdapter | None:
    """The adapter used for online payments: the configured provider, if it is available here."""
    adapters = available()
    return adapters.get(settings.PAYMENTS_ONLINE_PROVIDER) or None
