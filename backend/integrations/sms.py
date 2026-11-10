"""SMS provider adapters (MTS §6 `integrations`; M11).

P-08 (email and SMS providers) is still open, so the only adapter is `log`: it writes the message to the
application log and sends nothing. A real provider (for example a Pakistani SMS gateway or Twilio) is added as one
more class with the same `send` signature and selected with SMS_PROVIDER; no other code changes. Messages are
sent only for order updates the customer opted into (ConsentPurpose.SMS_UPDATES), never for marketing.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

from django.conf import settings

log = logging.getLogger("aurevon.sms")


@dataclass(frozen=True)
class Sent:
    provider: str
    message_id: str


class SmsProvider(Protocol):
    code: str

    def send(self, to: str, text: str) -> Sent: ...


class LogSms:
    """Development and pre-P-08 stand-in: records that a message would have gone out."""

    code = "log"

    def send(self, to: str, text: str) -> Sent:
        masked = to[:4] + "*" * max(len(to) - 7, 0) + to[-3:]
        log.info("sms not sent (no provider configured)", extra={"to": masked, "chars": len(text)})
        return Sent(self.code, "")


PROVIDERS: dict[str, type[SmsProvider]] = {"log": LogSms}


def provider() -> SmsProvider:
    code = getattr(settings, "SMS_PROVIDER", "log") or "log"
    cls = PROVIDERS.get(code)
    if cls is None:
        raise RuntimeError(f"Unknown SMS_PROVIDER {code!r}")
    return cls()
