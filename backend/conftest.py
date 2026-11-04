from collections.abc import Iterator

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.permissions import RoleCode
from apps.accounts.tests.factories import Staff, make_staff, sign_in


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture(autouse=True)
def _clean_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _send_mail_immediately(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests run inside a transaction that never commits, so on_commit email would never fire.
    Send at once instead; the commit-only behaviour itself is tested in apps/notifications/tests."""
    if "real_on_commit" in request.keywords:
        return
    monkeypatch.setattr("apps.notifications.services.transaction.on_commit", lambda fn, robust=False: fn())


@pytest.fixture
def owner(db: None) -> Staff:
    return make_staff(RoleCode.OWNER, "owner@aurevon.test")


@pytest.fixture
def owner2(db: None) -> Staff:
    return make_staff(RoleCode.OWNER, "owner2@aurevon.test")


@pytest.fixture
def owner_client(owner: Staff) -> APIClient:
    return sign_in(owner)
