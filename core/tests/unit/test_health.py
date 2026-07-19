"""The health endpoint backs the external uptime monitor: 200 means "app AND
database are serving", 503 means degraded — a bare liveness ping would report
"up" straight through a database outage."""

from unittest.mock import patch

import pytest

HEALTH_URL = "/api/v1/health/"


@pytest.mark.django_db
class TestHealthCheck:
    def test_healthy_when_the_database_answers(self, api_client):
        response = api_client.get(HEALTH_URL)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_degraded_when_the_database_is_down(self, api_client):
        with patch("core.urls.connection") as mock_connection:
            mock_connection.cursor.side_effect = Exception("db down")
            response = api_client.get(HEALTH_URL)
        assert response.status_code == 503
        # No error detail — the endpoint is public.
        assert response.json() == {"status": "degraded"}

    def test_head_works_for_monitors(self, api_client):
        # Uptime monitors often probe with HEAD to save bandwidth.
        assert api_client.head(HEALTH_URL).status_code == 200

    def test_head_degraded_when_the_database_is_down(self, api_client):
        # A HEAD-probing monitor must also see the outage — 200 here would
        # report "up" straight through a database failure.
        with patch("core.urls.connection") as mock_connection:
            mock_connection.cursor.side_effect = Exception("db down")
            assert api_client.head(HEALTH_URL).status_code == 503
