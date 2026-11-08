from unittest import mock

import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_reports_database_ok_and_degraded_when_others_down():
    with mock.patch("core.services.check_redis", return_value={"status": "error"}), \
         mock.patch("core.services.check_ollama", return_value={"status": "error"}):
        response = Client().get("/api/v1/system/health/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"]["status"] == "ok"


@pytest.mark.django_db
def test_health_all_ok():
    ok = {"status": "ok"}
    with mock.patch("core.services.check_redis", return_value=ok), \
         mock.patch("core.services.check_ollama", return_value=ok):
        body = Client().get("/api/v1/system/health/").json()
    assert body["status"] == "ok"


def test_health_returns_503_when_database_down():
    down = {"status": "error"}
    with mock.patch("core.views.run_all_checks",
                    return_value={"database": down, "redis": down, "ollama": down}):
        response = Client().get("/api/v1/system/health/")
    assert response.status_code == 503


def test_cors_only_allows_configured_origin():
    ok = {"status": "ok"}
    with mock.patch("core.views.run_all_checks",
                    return_value={"database": ok, "redis": ok, "ollama": ok}):
        good = Client().get("/api/v1/system/health/", headers={"Origin": "http://localhost:5173"})
        bad = Client().get("/api/v1/system/health/", headers={"Origin": "http://evil.example"})
    assert good["Access-Control-Allow-Origin"] == "http://localhost:5173"
    assert "Access-Control-Allow-Origin" not in bad