"""Top-level routes. The proxy sends /api/v1/ here (MTS v2.1 A-27); /health/ is internal only."""

from django.urls import include, path

from common import views

urlpatterns = [
    path("api/v1/", include("config.api_urls")),
    path("health/live", views.health_live, name="health-live"),
    path("health/ready", views.health_ready, name="health-ready"),
]

handler400 = "common.views.error_400"
handler403 = "common.views.error_403"
handler404 = "common.views.error_404"
handler500 = "common.views.error_500"
