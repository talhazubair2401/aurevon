"""Request ID middleware: every request and log line carries one ID (MTS §5 observability)."""

import re
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from common.request_context import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"
# Accept an upstream ID (from the proxy or CDN) only if it is short and plain, so logs can't be polluted.
_VALID_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class RequestIDMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        request.request_id = request_id  # type: ignore[attr-defined]
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[REQUEST_ID_HEADER] = request_id
        return response
