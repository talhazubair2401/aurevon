"""Routes under /api/v1/. Each module adds its own include here as it is built."""

from django.conf import settings
from django.urls import URLPattern, URLResolver, include, path, re_path
from drf_spectacular.views import SpectacularAPIView

from apps.accounts.api.urls import customer_urlpatterns, staff_urlpatterns
from common.views import ApiIndexView, api_not_found

urlpatterns: list[URLPattern | URLResolver] = [
    path("", ApiIndexView.as_view(), name="api-index"),
    # Staff API: only the staff session cookie is honoured here (MTS v2.1 A-22, §9).
    path("staff/", include(staff_urlpatterns)),
    *customer_urlpatterns,
]

if settings.API_SCHEMA_PUBLIC:
    urlpatterns.append(path("schema/", SpectacularAPIView.as_view(), name="api-schema"))

# Must stay last: unknown API paths always get a problem-details 404, even when DEBUG is on.
urlpatterns.append(re_path(r"^.*$", api_not_found, name="api-not-found"))
