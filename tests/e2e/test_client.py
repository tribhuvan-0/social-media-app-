"""
SocialApp E2E Test Client
Provides an opaque-box HTTP API client strictly interacting with the REST API.
"""

import json
import os
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import requests
except ImportError:
    requests = None


class ApiResponse:
    """Wrapper around HTTP responses providing contract inspection and assertions."""

    def __init__(self, status_code: int, text: str, headers: Dict[str, str]):
        self.status_code = status_code
        self.text = text
        self.headers = headers
        self._data = None
        self._parsed = False

    @property
    def data(self) -> Any:
        if not self._parsed:
            if self.text and self.text.strip():
                try:
                    self._data = json.loads(self.text)
                except Exception:
                    self._data = None
            else:
                self._data = None
            self._parsed = True
        return self._data

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def is_error(self) -> bool:
        return self.status_code >= 400

    def assert_status(self, expected_code: int, msg: Optional[str] = None):
        """Assert that status code matches expected value."""
        if self.status_code != expected_code:
            error_detail = f"Expected status {expected_code}, got {self.status_code}. Response: {self.text}"
            if msg:
                error_detail = f"{msg} - {error_detail}"
            raise AssertionError(error_detail)
        return self

    def assert_ok(self, msg: Optional[str] = None):
        return self.assert_status(200, msg)

    def assert_created(self, msg: Optional[str] = None):
        return self.assert_status(201, msg)

    def assert_no_content(self, msg: Optional[str] = None):
        return self.assert_status(204, msg)

    def assert_error(
        self,
        expected_code: int,
        message_substr: Optional[str] = None,
        field_error_name: Optional[str] = None,
    ):
        """Assert error response code and error envelope fields per docs.md."""
        self.assert_status(expected_code)
        data = self.data
        if not isinstance(data, dict):
            raise AssertionError(f"Expected JSON error object, got: {self.text}")

        # Check standard fields: status, message
        if "status" in data and data["status"] != expected_code:
            raise AssertionError(
                f"Error envelope status {data.get('status')} does not match HTTP status {expected_code}"
            )

        if message_substr and message_substr.lower() not in data.get("message", "").lower():
            raise AssertionError(
                f"Expected '{message_substr}' in error message '{data.get('message')}'"
            )

        if field_error_name:
            field_errors = data.get("fieldErrors")
            if not isinstance(field_errors, (dict, list)):
                raise AssertionError(
                    f"Expected 'fieldErrors' containing '{field_error_name}', got {field_errors}"
                )
            if isinstance(field_errors, dict) and field_error_name not in field_errors:
                raise AssertionError(f"Field error '{field_error_name}' not in {field_errors}")
            elif isinstance(field_errors, list):
                # If list of objects e.g. [{"field": "...", "message": "..."}]
                fields = [f.get("field") for f in field_errors if isinstance(f, dict)]
                if field_error_name not in fields:
                    raise AssertionError(
                        f"Field error '{field_error_name}' not in field list {fields}"
                    )
        return self


class ApiClient:
    """Opaque-box REST client for SocialApp backend."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.base_url = (base_url or os.environ.get("BASE_URL", "http://localhost:8080/api")).rstrip("/")
        self.token = token
        self.timeout = timeout
        self.session = requests.Session() if requests else None

    def set_token(self, token: Optional[str]):
        """Sets or clears the Bearer JWT."""
        self.token = token

    def clear_token(self):
        """Clears current JWT."""
        self.token = None

    def _resolve_url(self, path: str) -> str:
        """Resolves full URL from endpoint path."""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _get_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def request(
        self,
        method: str,
        path: str,
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        is_binary: bool = False,
    ) -> ApiResponse:
        """Executes an HTTP request."""
        url = self._resolve_url(path)
        req_headers = self._get_headers(headers)

        body = None
        if data is not None:
            if is_binary:
                body = data
            elif isinstance(data, (dict, list)):
                body = json.dumps(data)
            else:
                body = str(data)

        if requests and self.session:
            resp = self.session.request(
                method=method.upper(),
                url=url,
                data=body,
                params=params,
                headers=req_headers,
                timeout=self.timeout,
            )
            return ApiResponse(resp.status_code, resp.text, dict(resp.headers))
        else:
            # Standard library urllib fallback
            import urllib.request
            import urllib.error

            if params:
                query_string = urllib.parse.urlencode(
                    {k: str(v) for k, v in params.items() if v is not None}
                )
                url = f"{url}?{query_string}"

            req = urllib.request.Request(
                url=url,
                data=body.encode("utf-8") if isinstance(body, str) else body,
                headers=req_headers,
                method=method.upper(),
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_body = resp.read().decode("utf-8", errors="replace")
                    return ApiResponse(resp.status, resp_body, dict(resp.headers))
            except urllib.error.HTTPError as e:
                resp_body = e.read().decode("utf-8", errors="replace")
                return ApiResponse(e.code, resp_body, dict(e.headers))

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> ApiResponse:
        return self.request("GET", path, params=params, headers=headers)

    def post(self, path: str, data: Optional[Any] = None, headers: Optional[Dict[str, str]] = None) -> ApiResponse:
        return self.request("POST", path, data=data, headers=headers)

    def put(self, path: str, data: Optional[Any] = None, headers: Optional[Dict[str, str]] = None) -> ApiResponse:
        return self.request("PUT", path, data=data, headers=headers)

    def delete(self, path: str, headers: Optional[Dict[str, str]] = None) -> ApiResponse:
        return self.request("DELETE", path, headers=headers)

    def put_binary(self, upload_url: str, data: bytes, content_type: str) -> ApiResponse:
        """
        Direct binary PUT to presigned R2 or local-storage URL.
        Crucial: docs.md requires DO NOT send Authorization header to R2/upload URL.
        """
        url = upload_url
        if not (url.startswith("http://") or url.startswith("https://")):
            # Local fallback relative path like /api/uploads/local-storage/...
            # Derive host/port from base_url
            parsed = urllib.parse.urlparse(self.base_url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            url = f"{origin}{url if url.startswith('/') else '/' + url}"

        headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(data)),
        }

        if requests and self.session:
            resp = requests.put(url, data=data, headers=headers, timeout=self.timeout)
            return ApiResponse(resp.status_code, resp.text, dict(resp.headers))
        else:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(
                url=url,
                data=data,
                headers=headers,
                method="PUT",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    resp_body = resp.read().decode("utf-8", errors="replace")
                    return ApiResponse(resp.status, resp_body, dict(resp.headers))
            except urllib.error.HTTPError as e:
                resp_body = e.read().decode("utf-8", errors="replace")
                return ApiResponse(e.code, resp_body, dict(e.headers))

    # ==========================================
    # High-level REST API Endpoints (docs.md)
    # ==========================================

    # --- 1. Auth ---
    def signup(self, username: str, email: str, password: str) -> ApiResponse:
        return self.post("/auth/signup", {"username": username, "email": email, "password": password})

    def login(self, username: str, password: str) -> ApiResponse:
        return self.post("/auth/login", {"username": username, "password": password})

    def get_me(self) -> ApiResponse:
        return self.get("/auth/me")

    def change_password(self, old_password: str, new_password: str) -> ApiResponse:
        return self.put("/auth/password", {"oldPassword": old_password, "newPassword": new_password})

    # --- 2. Feed & Suggested ---
    def get_feed(self, page: int = 0, size: int = 10) -> ApiResponse:
        return self.get("/feed", params={"page": page, "size": size})

    def get_suggested_users(self) -> ApiResponse:
        return self.get("/users/suggested")

    # --- 3. Stories ---
    def get_stories(self) -> ApiResponse:
        return self.get("/stories")

    def mark_story_seen(self, story_id: int) -> ApiResponse:
        return self.post(f"/stories/{story_id}/seen")

    # --- 4. Reels ---
    def get_reels(self, size: int = 5, exclude: Optional[str] = None) -> ApiResponse:
        params: Dict[str, Any] = {"size": size}
        if exclude:
            params["exclude"] = exclude
        return self.get("/reels", params=params)

    # --- 5. Media & Social Actions ---
    def get_media(self, media_id: int) -> ApiResponse:
        return self.get(f"/media/{media_id}")

    def delete_media(self, media_id: int) -> ApiResponse:
        return self.delete(f"/media/{media_id}")

    def like_media(self, media_id: int) -> ApiResponse:
        return self.post(f"/media/{media_id}/like")

    def unlike_media(self, media_id: int) -> ApiResponse:
        return self.delete(f"/media/{media_id}/like")

    def share_media(self, media_id: int) -> ApiResponse:
        return self.post(f"/media/{media_id}/share")

    def record_view(self, media_id: int, watch_ms: int, duration_ms: int, completed: bool) -> ApiResponse:
        return self.post(f"/media/{media_id}/view", {
            "watchMs": watch_ms,
            "durationMs": duration_ms,
            "completed": completed,
        })

    def get_comments(self, media_id: int, page: int = 0, size: int = 20) -> ApiResponse:
        return self.get(f"/media/{media_id}/comments", params={"page": page, "size": size})

    def add_comment(self, media_id: int, text: str) -> ApiResponse:
        return self.post(f"/media/{media_id}/comments", {"text": text})

    def delete_comment(self, comment_id: int) -> ApiResponse:
        return self.delete(f"/comments/{comment_id}")

    # --- 6. Users & Social Graph ---
    def get_user_profile(self, user_id: int) -> ApiResponse:
        return self.get(f"/users/{user_id}/profile")

    def get_user_posts(self, user_id: int, page: int = 0, size: int = 18) -> ApiResponse:
        return self.get(f"/users/{user_id}/posts", params={"page": page, "size": size})

    def get_user_followers(self, user_id: int, page: int = 0, size: int = 20) -> ApiResponse:
        return self.get(f"/users/{user_id}/followers", params={"page": page, "size": size})

    def get_user_following(self, user_id: int, page: int = 0, size: int = 20) -> ApiResponse:
        return self.get(f"/users/{user_id}/following", params={"page": page, "size": size})

    def follow_user(self, user_id: int) -> ApiResponse:
        return self.post(f"/users/{user_id}/follow")

    def unfollow_user(self, user_id: int) -> ApiResponse:
        return self.delete(f"/users/{user_id}/follow")

    def update_profile(self, username: Optional[str] = None, bio: Optional[str] = None) -> ApiResponse:
        payload: Dict[str, Any] = {}
        if username is not None:
            payload["username"] = username
        if bio is not None:
            payload["bio"] = bio
        return self.put("/users/me", payload)

    def update_avatar(self, r2_key: str) -> ApiResponse:
        return self.put("/users/me/avatar", {"r2Key": r2_key})

    def update_settings(self, is_private: bool, notifications_enabled: bool) -> ApiResponse:
        return self.put("/users/me/settings", {
            "isPrivate": is_private,
            "notificationsEnabled": notifications_enabled,
        })

    def get_follow_requests(self, page: int = 0, size: int = 20) -> ApiResponse:
        return self.get("/follow-requests", params={"page": page, "size": size})

    def accept_follow_request(self, user_id: int) -> ApiResponse:
        return self.post(f"/follow-requests/{user_id}/accept")

    def decline_follow_request(self, user_id: int) -> ApiResponse:
        return self.post(f"/follow-requests/{user_id}/decline")

    # --- 7. Uploads ---
    def presign_upload(self, file_name: str, content_type: str, upload_type: str, file_size: int) -> ApiResponse:
        return self.post("/uploads/presign", {
            "fileName": file_name,
            "contentType": content_type,
            "type": upload_type,
            "fileSize": file_size,
        })

    def confirm_upload(self, r2_key: str, upload_type: str, caption: Optional[str] = None) -> ApiResponse:
        payload: Dict[str, Any] = {
            "r2Key": r2_key,
            "type": upload_type,
        }
        if caption is not None:
            payload["caption"] = caption
        return self.post("/uploads/confirm", payload)
