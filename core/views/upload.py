"""
Upload views — generates Cloudinary signed upload parameters.

The frontend calls this endpoint to get a short-lived signature, then
posts the image file directly to Cloudinary's API. Django never handles
the binary file data.
"""

import time

import cloudinary
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

ALLOWED_FOLDERS = {"oiueei/users", "oiueei/things", "oiueei/collections", "oiueei/documents"}


class CloudinarySignatureView(APIView):
    """
    POST /api/v1/upload/signature/

    Returns a signed set of upload parameters for a direct browser-to-Cloudinary upload.

    Request body:
        { "folder": "oiueei/things" }

    Response:
        {
            "signature": "...",
            "timestamp": 1234567890,
            "api_key": "...",
            "cloud_name": "..."
        }
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="30/h", method="POST", block=True))
    def post(self, request):
        folder = request.data.get("folder", "oiueei/users")
        if folder not in ALLOWED_FOLDERS:
            folder = "oiueei/users"

        resource_type = request.data.get("resource_type", "image")
        if resource_type not in ("image", "raw"):
            resource_type = "image"

        timestamp = int(time.time())
        params_to_sign = {"folder": folder, "timestamp": timestamp}

        signature = cloudinary.utils.api_sign_request(
            params_to_sign, cloudinary.config().api_secret
        )

        return Response(
            {
                "signature": signature,
                "timestamp": timestamp,
                "api_key": cloudinary.config().api_key,
                "cloud_name": cloudinary.config().cloud_name,
                "folder": folder,
                "resource_type": resource_type,
            }
        )
