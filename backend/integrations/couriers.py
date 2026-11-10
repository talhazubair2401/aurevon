"""Courier adapters (MTS §8 integration layer, §10 delivery). Business code talks only to this interface.

The courier choice (P-07) is still open, so the only adapter is `manual` (the MTS §10 manual fallback): staff book
the parcel with the courier themselves and record its tracking number; tracking updates are entered by staff.
A real courier is one adapter class here (booking, tracking events, label) plus its credentials, registered in
COURIERS, with no change to orders or shipping.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class Booking:
    tracking_number: str
    tracking_url: str


@dataclass(frozen=True)
class CourierEvent:
    status: str  # a shipping.ShipmentStatus value
    occurred_at: datetime
    description: str = ""
    location: str = ""
    external_id: str = ""


class Courier(Protocol):
    code: str
    label: str
    books_automatically: bool

    def book(self, order_number: str, tracking_number: str, tracking_url: str) -> Booking: ...

    def events(self, tracking_number: str) -> list[CourierEvent]: ...


class ManualCourier:
    """Staff book with the courier outside AureVon and type in the tracking number (and link, if any)."""

    code = "manual"
    label = "Manual (tracking entered by staff)"
    books_automatically = False

    def book(self, order_number: str, tracking_number: str, tracking_url: str) -> Booking:
        return Booking(tracking_number=tracking_number.strip(), tracking_url=tracking_url.strip())

    def events(self, tracking_number: str) -> list[CourierEvent]:
        return []  # updates come from staff


COURIERS: dict[str, Courier] = {c.code: c for c in (ManualCourier(),)}


def get(code: str) -> Courier | None:
    return COURIERS.get(code)
