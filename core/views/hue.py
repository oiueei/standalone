"""
Philips Hue easter egg — controls a Hue light via the Hue Cloud API.

Routes:
  GET /api/v1/hue/trigger/            — start blinking a light
  GET /api/v1/hue/stop/               — stop blinking and turn off
  GET /api/v1/hue/lights/             — list available lights
  GET /api/v1/hue/set-refresh-token/  — inject a new refresh token (admin)

All env vars are optional — endpoints return a clear error if any are missing.
"""

import logging
import os
import threading
import time

import requests
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

HUE_API_BASE = "https://api.meethue.com/route/api"

blink_active = False

_token_cache = {
    "access_token": None,
    "refresh_token": None,
    "expires_at": 0,
}


def _bootstrap_token_cache():
    stored_token = os.environ.get("HUE_ACCESS_TOKEN")
    stored_expiry = os.environ.get("HUE_ACCESS_TOKEN_EXPIRES_AT")
    stored_refresh = os.environ.get("HUE_REFRESH_TOKEN")
    if stored_token and stored_expiry:
        try:
            expires_at = float(stored_expiry)
            if time.time() < expires_at - 60:
                _token_cache["access_token"] = stored_token
                _token_cache["expires_at"] = expires_at
                _token_cache["refresh_token"] = stored_refresh
                logger.info("Hue: loaded valid access token from env")
                return
        except ValueError:
            pass
    logger.info("Hue: no valid stored access token, will refresh on first request")


_bootstrap_token_cache()


def _get_access_token():
    """Return a valid access token, refreshing only when expired."""
    now = time.time()
    if _token_cache["access_token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["access_token"]

    refresh_token = _token_cache["refresh_token"] or os.environ.get("HUE_REFRESH_TOKEN")
    client_id = os.environ.get("HUE_CLIENT_ID")
    client_secret = os.environ.get("HUE_CLIENT_SECRET")

    response = requests.post(
        "https://api.meethue.com/v2/oauth2/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        auth=(client_id, client_secret),
    )
    data = response.json()
    logger.info(f"Hue token refresh: {response.status_code}")

    if response.status_code == 200 and "access_token" in data:
        expires_at = now + data.get("expires_in", 604800)
        _token_cache["access_token"] = data["access_token"]
        _token_cache["refresh_token"] = data["refresh_token"]
        _token_cache["expires_at"] = expires_at
        return _token_cache["access_token"]

    logger.error(f"Hue token refresh failed: {response.status_code} — {response.text}")
    return None


def _missing_vars():
    required = ["HUE_REFRESH_TOKEN", "HUE_CLIENT_ID", "HUE_CLIENT_SECRET", "HUE_USERNAME"]
    return [v for v in required if not os.environ.get(v)]


class HueTriggerView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        global blink_active

        missing = _missing_vars()
        if missing:
            return Response({"error": f"Missing env vars: {', '.join(missing)}"}, status=500)

        try:
            access_token = _get_access_token()
            if not access_token:
                return Response({"error": "Failed to obtain access token"}, status=500)

            hue_username = os.environ.get("HUE_USERNAME")
            light_id = os.environ.get("HUE_LIGHT_ID", "3")
            blink_active = True

            def blink_loop():
                global blink_active
                headers = {"Authorization": f"Bearer {access_token}"}
                url = f"{HUE_API_BASE}/{hue_username}/lights/{light_id}/state"
                while blink_active:
                    requests.put(url, json={"on": True, "bri": 254}, headers=headers)
                    time.sleep(1)
                    requests.put(url, json={"on": False}, headers=headers)
                    time.sleep(1)

            threading.Thread(target=blink_loop, daemon=True).start()
            return Response({"status": "blinking — call /api/v1/hue/stop/ to stop"})
        except Exception as e:
            logger.exception("Hue trigger failed")
            return Response({"error": str(e)}, status=500)


class HueStopView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        global blink_active
        blink_active = False

        try:
            access_token = _get_access_token()
            if access_token:
                hue_username = os.environ.get("HUE_USERNAME")
                light_id = os.environ.get("HUE_LIGHT_ID", "3")
                headers = {"Authorization": f"Bearer {access_token}"}
                url = f"{HUE_API_BASE}/{hue_username}/lights/{light_id}/state"
                requests.put(url, json={"on": False, "alert": "none"}, headers=headers)
        except Exception:
            logger.exception("Hue stop failed")

        return Response({"status": "stopped"})


class HueLightsView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        missing = _missing_vars()
        if missing:
            return Response({"error": f"Missing env vars: {', '.join(missing)}"}, status=500)

        try:
            access_token = _get_access_token()
            if not access_token:
                return Response({"error": "Failed to obtain access token"}, status=500)

            hue_username = os.environ.get("HUE_USERNAME")
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(f"{HUE_API_BASE}/{hue_username}/lights", headers=headers)
            lights_data = response.json()

            result = {
                lid: {
                    "name": info.get("name"),
                    "type": info.get("type"),
                    "on": info.get("state", {}).get("on"),
                    "brightness": info.get("state", {}).get("bri"),
                    "reachable": info.get("state", {}).get("reachable"),
                }
                for lid, info in lights_data.items()
            }
            return Response(result)
        except Exception as e:
            logger.exception("Hue lights list failed")
            return Response({"error": str(e)}, status=500)


class HueSetRefreshTokenView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        admin_key = os.environ.get("ADMIN_KEY")
        if admin_key and request.query_params.get("key") != admin_key:
            return Response({"error": "Unauthorized"}, status=401)

        new_token = request.query_params.get("token")
        if not new_token:
            return Response({"error": "Missing ?token= parameter"}, status=400)

        _token_cache["access_token"] = None
        _token_cache["refresh_token"] = new_token
        _token_cache["expires_at"] = 0
        logger.info("Hue refresh token manually updated")
        return Response({"status": "refresh token updated"})
