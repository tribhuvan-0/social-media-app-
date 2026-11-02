"""
SocialApp E2E Test Helpers
Provides fixture factories, deterministic test data generators, and upload workflow helpers.
"""

import os
import uuid
from typing import Any, Dict, Optional, Tuple

from tests.e2e.test_client import ApiClient, ApiResponse

# Minimal valid dummy binary payloads
MINIMAL_JPEG_BYTES = (
    b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
    b"\xFF\xDB\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c"
    b"\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c"
    b"\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xFF\xC0\x00\x0b\x08\x00"
    b"\x01\x00\x01\x01\x01\x11\x00\xFF\xC4\x00\x1f\x00\x00\x01\x05\x01\x01"
    b"\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05"
    b"\x06\x07\x08\t\n\x0b\xFF\xDA\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xFF\xD9"
)

MINIMAL_MP4_BYTES = (
    b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41\x00\x00\x00\x08free"
    b"\x00\x00\x00\x08mdat\x00\x00\x00\x28moov\x00\x00\x00\x6cmvhd\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\xe8\x00\x00\x00\x00\x00\x01"
    b"\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00"
)


def generate_unique_suffix() -> str:
    """Generates a short unique hex string."""
    return uuid.uuid4().hex[:10]


def generate_user_credentials(prefix: str = "usr") -> Tuple[str, str, str]:
    """
    Generates valid credentials complying with:
    - username: 3-30 chars, lowercase alphanumeric + underscore
    - email: standard email format
    - password: min 8 chars, at least 1 letter and 1 digit
    """
    uid = generate_unique_suffix()
    username = f"{prefix}_{uid}"[:30].lower()
    email = f"{username}@testdomain.internal"
    password = f"TestPass123_{uid[:4]}"
    return username, email, password


def create_test_user(
    base_url: Optional[str] = None,
    is_private: bool = False,
    bio: Optional[str] = None,
    prefix: str = "usr",
) -> Tuple[ApiClient, Dict[str, Any], str]:
    """
    Provisions a new test user via POST /auth/signup.
    Returns:
        (client with token configured, Me user dict, plaintext password)
    """
    client = ApiClient(base_url=base_url)
    username, email, password = generate_user_credentials(prefix=prefix)

    resp = client.signup(username=username, email=email, password=password)
    resp.assert_created(f"Signup failed for {username}")

    data = resp.data
    token = data.get("token")
    user = data.get("user")
    if not token or not user:
        raise AssertionError(f"Invalid signup response structure: {data}")

    client.set_token(token)

    # Apply settings if needed
    if is_private:
        sett_resp = client.update_settings(is_private=True, notifications_enabled=True)
        sett_resp.assert_ok("Failed to set user private")
        user["isPrivate"] = True

    if bio:
        bio_resp = client.update_profile(bio=bio)
        bio_resp.assert_ok("Failed to set user bio")
        user["bio"] = bio

    return client, user, password


def upload_media_helper(
    client: ApiClient,
    upload_type: str = "POST",
    content_type: str = "image/jpeg",
    file_bytes: Optional[bytes] = None,
    caption: str = "E2E Test media #social #e2e",
    file_name: Optional[str] = None,
) -> Tuple[ApiResponse, Dict[str, Any]]:
    """
    Executes the 3-step upload pipeline:
    1. POST /uploads/presign
    2. PUT binary data to uploadUrl
    3. POST /uploads/confirm
    Returns (confirm_response, media_card_dict).
    """
    if file_bytes is None:
        if content_type == "video/mp4":
            file_bytes = MINIMAL_MP4_BYTES
            ext = "mp4"
        else:
            file_bytes = MINIMAL_JPEG_BYTES
            ext = "jpg"
    else:
        ext = "mp4" if "video" in content_type else "jpg"

    if file_name is None:
        file_name = f"test_{generate_unique_suffix()}.{ext}"

    # Step 1: Presign
    presign_resp = client.presign_upload(
        file_name=file_name,
        content_type=content_type,
        upload_type=upload_type,
        file_size=len(file_bytes),
    )
    presign_resp.assert_ok(f"Presign failed for {upload_type}")
    presign_data = presign_resp.data
    upload_url = presign_data.get("uploadUrl")
    r2_key = presign_data.get("r2Key")

    if not upload_url or not r2_key:
        raise AssertionError(f"Presign response missing uploadUrl or r2Key: {presign_data}")

    # Step 2: Binary PUT
    put_resp = client.put_binary(upload_url, data=file_bytes, content_type=content_type)
    if put_resp.status_code not in (200, 201, 204):
        raise AssertionError(
            f"Binary upload failed with status {put_resp.status_code}: {put_resp.text}"
        )

    # Step 3: Confirm
    confirm_resp = client.confirm_upload(
        r2_key=r2_key,
        upload_type=upload_type,
        caption=caption if upload_type != "AVATAR" else None,
    )
    confirm_resp.assert_created(f"Confirm failed for {r2_key}")
    return confirm_resp, confirm_resp.data
