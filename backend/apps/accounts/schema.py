"""OpenAPI descriptions of the two session cookies, so the generated client documents which realm each call uses."""

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension

from .services.sessions import CUSTOMER_COOKIE, STAFF_COOKIE


class StaffSessionScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = "apps.accounts.authentication.StaffSessionAuthentication"
    name = "staffSession"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {"type": "apiKey", "in": "cookie", "name": STAFF_COOKIE}


class CustomerSessionScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    target_class = "apps.accounts.authentication.CustomerSessionAuthentication"
    name = "customerSession"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        return {"type": "apiKey", "in": "cookie", "name": CUSTOMER_COOKIE}
