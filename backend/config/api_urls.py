"""Routes under /api/v1/. Each module adds its own include here as it is built."""

from django.conf import settings
from django.urls import URLPattern, URLResolver, path, re_path
from drf_spectacular.views import SpectacularAPIView

from common.views import ApiIndexView, api_not_found

urlpatterns: list[URLPattern | URLResolver] = [
    path("", ApiIndexView.as_view(), name="api-index"),
]

if settings.API_SCHEMA_PUBLIC:
    urlpatterns.append(path("schema/", SpectacularAPIView.as_view(), name="api-schema"))

# Must stay last: unknown API paths always get a problem-details 404, even when DEBUG is on.
urlpatterns.append(re_path(r"^.*$", api_not_found, name="api-not-found"))
