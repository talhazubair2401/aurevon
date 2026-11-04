"""Receives Content Security Policy violation reports from browsers (decision 0005, D-08; MTS §12, §14).

Both report formats are accepted: the legacy `report-uri` body (`{"csp-report": {...}}`, application/csp-report)
and the Reporting API batch (a JSON list of `{"type": "csp-violation", "body": {...}}`). Reports are untrusted
input: size-capped, rate-limited per address, reduced to a few known fields and logged for monitoring. Nothing is
stored and nothing is echoed back.
"""

import json
import logging
from typing import Any

from django.http import HttpRequest, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from common.security import Limit, client_ip, hit

logger = logging.getLogger("aurevon.csp")

MAX_BODY_BYTES = 16 * 1024
MAX_REPORTS_PER_REQUEST = 20
RATE_LIMIT = Limit(count=60, window=60)
_FIELDS = {
    # legacy name -> Reporting API name
    "document-uri": "documentURL",
    "effective-directive": "effectiveDirective",
    "violated-directive": "effectiveDirective",
    "blocked-uri": "blockedURL",
    "disposition": "disposition",
    "source-file": "sourceFile",
    "line-number": "lineNumber",
}


def _clean(value: Any) -> str | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        # Never log query strings: they can carry tokens or personal data.
        return value.split("?", 1)[0].split("#", 1)[0][:300]
    return None


def _normalise(body: dict[str, Any], legacy: bool) -> dict[str, str | int | None]:
    out: dict[str, str | int | None] = {}
    for legacy_name, modern_name in _FIELDS.items():
        key = legacy_name if legacy else modern_name
        if key in body and modern_name not in out:
            out[modern_name] = _clean(body[key])
    return out


def parse_reports(raw: bytes) -> list[dict[str, str | int | None]]:
    data = json.loads(raw)
    if isinstance(data, dict) and isinstance(data.get("csp-report"), dict):
        return [_normalise(data["csp-report"], legacy=True)]
    if isinstance(data, list):
        return [
            _normalise(item["body"], legacy=False)
            for item in data[:MAX_REPORTS_PER_REQUEST]
            if isinstance(item, dict) and item.get("type") == "csp-violation" and isinstance(item.get("body"), dict)
        ]
    return []


@csrf_exempt  # browsers send these without cookies or tokens; the view changes no state
@require_POST
@never_cache
def csp_report(request: HttpRequest) -> HttpResponse:
    if int(request.META.get("CONTENT_LENGTH") or 0) > MAX_BODY_BYTES:
        return HttpResponse(status=413)
    if hit("csp-report", client_ip(request) or "unknown", RATE_LIMIT) > RATE_LIMIT.count:
        return HttpResponse(status=429)
    try:
        reports = parse_reports(request.body[:MAX_BODY_BYTES])
    except (ValueError, KeyError, TypeError):
        return HttpResponse(status=400)
    for report in reports:
        logger.warning("csp_violation", extra={"csp": report})
    return HttpResponse(status=204)
