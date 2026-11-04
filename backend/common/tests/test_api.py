import pytest

from common.exceptions import PROBLEM_CONTENT_TYPE

pytestmark = pytest.mark.django_db


def test_api_index_identifies_the_api(api_client):
    response = api_client.get("/api/v1/")
    assert response.status_code == 200
    assert response.json() == {"name": "AureVon API", "version": "v1"}


def test_unknown_api_path_returns_problem_json(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response["Content-Type"] == PROBLEM_CONTENT_TYPE
    body = response.json()
    assert body["status"] == 404 and body["title"] == "Not found"


def test_unknown_api_path_is_json_even_in_debug(client, settings):
    settings.DEBUG = True
    response = client.post("/api/v1/nothing/here", data={}, content_type="application/json")
    assert response.status_code == 404
    assert response["Content-Type"] == PROBLEM_CONTENT_TYPE


def test_django_admin_is_not_installed(client, settings):
    assert "django.contrib.admin" not in settings.INSTALLED_APPS
    assert client.get("/admin/").status_code == 404


def test_openapi_schema_is_generated(api_client):
    response = api_client.get("/api/v1/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "AureVon API"
    assert "/api/v1/" in schema["paths"]


@pytest.mark.urls("common.tests.urls")
def test_endpoints_deny_by_default(api_client):
    response = api_client.get("/api/v1/_test/protected")
    assert response.status_code == 403
    assert response["Content-Type"] == PROBLEM_CONTENT_TYPE
    assert response.json()["title"] == "Not allowed"


@pytest.mark.urls("common.tests.urls")
def test_validation_errors_use_problem_details(api_client):
    response = api_client.post("/api/v1/_test/validate", {"quantity": 0}, format="json")
    assert response.status_code == 400
    body = response.json()
    assert body["type"].endswith("/validation-error")
    assert body["title"] == "Invalid request"
    assert "quantity" in body["errors"]


@pytest.mark.urls("common.tests.urls")
def test_only_json_is_accepted(api_client):
    response = api_client.post("/api/v1/_test/validate", "quantity=2", content_type="application/x-www-form-urlencoded")
    assert response.status_code == 415
