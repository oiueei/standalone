"""
Upload views — generates Cloudinary signed upload parameters.

The frontend calls this endpoint to get a short-lived signature, then posts the
file directly to Cloudinary's API. Django never handles the binary file data.

The signature binds every upload parameter, so a client cannot change them
without breaking it (verified against the live account):

- ``public_id`` is generated server-side, so a client cannot choose an arbitrary
  id (which could overwrite another asset) — only store the id Cloudinary
  returns.
- ``allowed_formats`` restricts what Cloudinary will accept: raster photo formats
  only (SVG is excluded — it can carry script).
- ``resource_type`` is always ``image`` (never trusted from the client).

Note: Cloudinary's ``max_file_size`` upload parameter is not enforced on this
account/plan (verified), so the per-file size cap stays a client-side check.
"""

import secrets
import time

import cloudinary
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

ALLOWED_FOLDERS = {"oiueei/users", "oiueei/things", "oiueei/collections"}

# Raster photo formats only — SVG and other script-bearing/non-photo formats are
# excluded so an <img>-rendered upload can never carry active content.
IMAGE_FORMATS = "jpg,jpeg,png,webp,gif,heic,heif,avif,bmp,tif,tiff"


class CloudinarySignatureView(APIView):
    """
    POST /api/v1/upload/signature/

    Returns a signed set of upload parameters for a direct browser-to-Cloudinary
    upload. The client must send back the signed parameters verbatim (folder,
    public_id, allowed_formats) alongside the file.

    Request body:
        { "folder": "oiueei/things" }

    Response:
        {
            "signature": "...",
            "timestamp": 1234567890,
            "api_key": "...",
            "cloud_name": "...",
            "folder": "oiueei/things",
            "public_id": "<server-generated>",
            "allowed_formats": "jpg,jpeg,png,...",
            "resource_type": "image"
        }
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="30/h", method="POST", block=True))
    def post(self, request):
        folder = request.data.get("folder", "oiueei/users")
        if folder not in ALLOWED_FOLDERS:
            folder = "oiueei/users"

        resource_type = "image"
        allowed_formats = IMAGE_FORMATS
        # Random id within the folder; `folder` is sent separately, so the public_id
        # itself carries no folder prefix (Cloudinary prepends `folder`).
        public_id = secrets.token_urlsafe(16)
        timestamp = int(time.time())

        params_to_sign = {
            "allowed_formats": allowed_formats,
            "folder": folder,
            "public_id": public_id,
            "timestamp": timestamp,
        }

        signature = cloudinary.utils.api_sign_request(
            params_to_sign, cloudinary.config().api_secret
        )

        response = {
            "signature": signature,
            "timestamp": timestamp,
            "api_key": cloudinary.config().api_key,
            "cloud_name": cloudinary.config().cloud_name,
            "folder": folder,
            "public_id": public_id,
            "allowed_formats": allowed_formats,
            "resource_type": resource_type,
        }

        return Response(response)
