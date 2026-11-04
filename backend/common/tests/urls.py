"""Test-only routes for exercising API-wide behaviour (default deny, error format)."""

from django.urls import include, path
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class _ProtectedView(APIView):
    """Declares no permission, so it inherits the default-deny setting."""

    def get(self, request: Request) -> Response:
        return Response({"secret": True})


class _EchoSerializer(serializers.Serializer[dict[str, int]]):
    quantity = serializers.IntegerField(min_value=1)


class _ValidatingView(APIView):
    permission_classes = []

    def post(self, request: Request) -> Response:
        s = _EchoSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(s.validated_data)


# Test routes first: config.api_urls ends with a catch-all 404.
urlpatterns = [
    path("api/v1/_test/protected", _ProtectedView.as_view()),
    path("api/v1/_test/validate", _ValidatingView.as_view()),
    path("api/v1/", include("config.api_urls")),
]
