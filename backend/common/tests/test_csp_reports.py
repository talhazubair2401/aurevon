import json
import logging
from typing import TYPE_CHECKING, Any

import pytest
from django.core.cache import cache
from django.test import Client

from common.csp_reports import RATE_LIMIT

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as Response

URL = "/api/v1/csp-reports"

LEGACY = {
    "csp-report": {
        "document-uri": "https://aurevon.example/en?token=secret",
        "effective-directive": "script-src-elem",
        "blocked-uri": "inline",
        "disposition": "enforce",
        "line-number": 3,
        "original-policy": "default-src 'self'",
    }
}
MODERN = [
    {
        "type": "csp-violation",
        "body": {
            "documentURL": "https://aurevon.example/ur",
            "effectiveDirective": "script-src-elem",
            "blockedURL": "https://evil.example/x.js",
            "disposition": "enforce",
        },
    },
    {"type": "deprecation", "body": {"id": "ignored"}},
]


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    cache.clear()


def post(client: Client, payload: Any, content_type: str = "application/csp-report") -> "Response":
    response: Response = client.post(URL, data=json.dumps(payload), content_type=content_type)
    return response


def test_legacy_report_is_accepted_and_logged_without_query_strings(client, caplog):
    with caplog.at_level(logging.WARNING, logger="aurevon.csp"):
        response = post(client, LEGACY)
    assert response.status_code == 204
    (record,) = caplog.records
    assert record.csp == {
        "documentURL": "https://aurevon.example/en",
        "effectiveDirective": "script-src-elem",
        "blockedURL": "inline",
        "disposition": "enforce",
        "lineNumber": 3,
    }


def test_reporting_api_batch_keeps_only_csp_violations(client, caplog):
    with caplog.at_level(logging.WARNING, logger="aurevon.csp"):
        response = post(client, MODERN, content_type="application/reports+json")
    assert response.status_code == 204
    assert [r.csp["blockedURL"] for r in caplog.records] == ["https://evil.example/x.js"]


def test_needs_no_csrf_token_or_session(client):
    strict = Client(enforce_csrf_checks=True)
    assert post(strict, LEGACY).status_code == 204


def test_only_post(client):
    assert client.get(URL).status_code == 405


def test_malformed_body_is_rejected(client):
    response = client.post(URL, data="not json", content_type="application/csp-report")
    assert response.status_code == 400


def test_oversized_body_is_rejected(client):
    response = client.post(URL, data="x" * 20_000, content_type="application/csp-report")
    assert response.status_code == 413


def test_rate_limited_per_address(client):
    for _ in range(RATE_LIMIT.count):
        assert post(client, LEGACY).status_code == 204
    assert post(client, LEGACY).status_code == 429


def test_response_is_never_cached(client):
    assert "no-store" in post(client, LEGACY)["Cache-Control"]
