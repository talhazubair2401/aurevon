import logging
import re

import pytest

pytestmark = pytest.mark.django_db


def test_generates_request_id_when_missing(client):
    response = client.get("/health/live")
    assert re.fullmatch(r"[0-9a-f]{32}", response["X-Request-ID"])


def test_keeps_a_valid_upstream_request_id(client):
    response = client.get("/health/live", HTTP_X_REQUEST_ID="edge-1234abcd")
    assert response["X-Request-ID"] == "edge-1234abcd"


@pytest.mark.parametrize("bad", ["short", "has spaces in it!", "x" * 65, "line\nbreak-123456"])
def test_replaces_an_unsafe_upstream_request_id(client, bad):
    response = client.get("/health/live", HTTP_X_REQUEST_ID=bad)
    assert response["X-Request-ID"] != bad


def test_log_records_carry_the_request_id(client, caplog, monkeypatch):
    logger = logging.getLogger("common.views")

    def failing_db():
        logger.error("probe")
        return False

    monkeypatch.setattr("common.views._check_database", failing_db)
    from common.logging import RequestIDFilter

    caplog.handler.addFilter(RequestIDFilter())
    with caplog.at_level(logging.ERROR, logger="common.views"):
        response = client.get("/health/ready", HTTP_X_REQUEST_ID="trace-abcdef12")
    record = next(r for r in caplog.records if r.getMessage() == "probe")
    assert record.request_id == "trace-abcdef12" == response["X-Request-ID"]
