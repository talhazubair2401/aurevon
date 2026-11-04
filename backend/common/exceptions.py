"""One error shape for the whole API: RFC 9457 problem details (MTS §8)."""

from typing import Any

from django.http import JsonResponse
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

PROBLEM_CONTENT_TYPE = "application/problem+json"
PROBLEM_TYPE_BASE = "https://aurevon.pk/problems/"


def problem(
    status_code: int, title: str, detail: str | None = None, code: str | None = None, **extra: Any
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": PROBLEM_TYPE_BASE + code if code else "about:blank",
        "title": title,
        "status": status_code,
    }
    if detail:
        body["detail"] = detail
    body.update(extra)
    return body


def problem_response(status_code: int, title: str, detail: str | None = None, code: str | None = None) -> JsonResponse:
    body = problem(status_code, title, detail, code)
    return JsonResponse(body, status=status_code, content_type=PROBLEM_CONTENT_TYPE)


def _first_message(detail: Any) -> str:
    if isinstance(detail, list) and detail:
        return _first_message(detail[0])
    if isinstance(detail, dict) and detail:
        return _first_message(next(iter(detail.values())))
    return str(detail)


def problem_details_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    response = exception_handler(exc, context)
    if response is None:
        return None  # unexpected errors become a 500 through Django's handler500

    if isinstance(exc, exceptions.ValidationError):
        body = problem(
            response.status_code,
            "Invalid request",
            "One or more fields are invalid.",
            code="validation-error",
            errors=exc.detail,
        )
    elif isinstance(exc, exceptions.APIException):
        code = exc.get_codes()
        body = problem(
            response.status_code,
            _title_for(response.status_code),
            _first_message(exc.detail),
            code=str(code).replace("_", "-") if isinstance(code, str) else None,
        )
    else:  # Http404 / PermissionDenied converted by DRF
        body = problem(response.status_code, _title_for(response.status_code), _first_message(response.data))

    response.data = body
    response.content_type = PROBLEM_CONTENT_TYPE
    return response


def _title_for(status_code: int) -> str:
    return {
        status.HTTP_400_BAD_REQUEST: "Bad request",
        status.HTTP_401_UNAUTHORIZED: "Not signed in",
        status.HTTP_403_FORBIDDEN: "Not allowed",
        status.HTTP_404_NOT_FOUND: "Not found",
        status.HTTP_405_METHOD_NOT_ALLOWED: "Method not allowed",
        status.HTTP_406_NOT_ACCEPTABLE: "Not acceptable",
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "Unsupported media type",
        status.HTTP_429_TOO_MANY_REQUESTS: "Too many requests",
    }.get(status_code, "Request failed")
