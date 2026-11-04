import pytest
from django.core import mail
from django.db import transaction

from apps.notifications.services import send_email
from apps.notifications.tasks import render

pytestmark = pytest.mark.django_db


@pytest.mark.real_on_commit
def test_email_is_sent_only_after_commit(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        send_email(["a@aurevon.test"], "staff_reactivated", {"account_email": "a@aurevon.test"})
        assert mail.outbox == []
    assert len(mail.outbox) == 1


@pytest.mark.real_on_commit
def test_rolled_back_changes_send_nothing(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        try:
            with transaction.atomic():
                send_email(["a@aurevon.test"], "staff_reactivated", {"account_email": "a@aurevon.test"})
                raise RuntimeError("roll back")
        except RuntimeError:
            pass
    assert callbacks == [] and mail.outbox == []


def test_links_are_not_html_escaped():
    _subject, body = render("staff_invite", {"link": "https://x.test/staff/enroll#token=a&b", "role": "Owner"})
    assert "#token=a&b" in body
