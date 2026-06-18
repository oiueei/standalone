"""
End-to-end check that a rate-limited endpoint returns 429 (not 403).

The rest of the suite runs with ``RATELIMIT_ENABLE = False``; here we turn it on
(with a real local-memory cache so counting works) and drive a real endpoint
past its limit through the full DRF stack, exercising the custom exception
handler (`core.exceptions.api_exception_handler`).
"""

from django.core.cache import caches
from django.test import override_settings


@override_settings(
    RATELIMIT_ENABLE=True,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "ratelimit-429-test",
        }
    },
)
def test_rate_limited_endpoint_returns_429(db, api_client):
    # request-link is limited to 5/min by IP; the 6th within the window blocks.
    caches["default"].clear()
    responses = [
        api_client.post("/api/v1/auth/request-link/", {"email": "rl@example.com"}, format="json")
        for _ in range(6)
    ]
    assert responses[0].status_code == 200
    assert responses[-1].status_code == 429  # not 403
    assert "detail" in responses[-1].data
