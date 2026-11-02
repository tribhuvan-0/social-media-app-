"""
REST API Client for the SocialApp desktop frontend.
Manages HTTP requests via requests.Session, holds JWT in memory only (never written to disk),
handles automatic Authorization header injection, request timeouts, error translation into ApiError,
session expiry (401 interceptor), and streaming direct binary uploads.
"""

import io
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import requests

from .config import API_BASE_URL, TIMEOUT_NORMAL, TIMEOUT_UPLOAD

logger = logging.getLogger("SocialApp.api")


class ApiError(Exception):
    """
    Structured API Error parsed from standard backend error JSON.
    Format: {"timestamp": "...", "status": 400, "error": "...", "message": "...", "fieldErrors": {...}}
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        field_errors: Optional[Dict[str, str]] = None,
        error_type: Optional[str] = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.field_errors = field_errors or {}
        self.error_type = error_type or "ApiError"

    def __str__(self) -> str:
        if self.field_errors:
            fields_desc = ", ".join(f"{k}: {v}" for k, v in self.field_errors.items())
            return f"[{self.status_code}] {self.message} ({fields_desc})"
        return f"[{self.status_code}] {self.message}"


class ProgressFileWrapper:
    """
    Streaming file reader that tracks byte progress and invokes a callback.
    Does NOT use chunked encoding; allows requests to read exact Content-Length.
    """

    def __init__(
        self,
        file_obj: Any,
        total_size: int,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> None:
        self._file_obj = file_obj
        self._total_size = total_size
        self._bytes_read = 0
        self._callback = progress_callback

    def read(self, size: int = -1) -> bytes:
        chunk = self._file_obj.read(size)
        if chunk:
            self._bytes_read += len(chunk)
            if self._callback:
                try:
                    self._callback(self._bytes_read, self._total_size)
                except Exception:
                    pass
        return chunk

    def __len__(self) -> int:
        return self._total_size


class ApiClient:
    """
    Authoritative HTTP REST Client communicating with the Spring Boot backend.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        on_unauthorized: Optional[Callable[[], None]] = None,
        player: Optional[Any] = None
    ) -> None:
        self.base_url = (base_url or API_BASE_URL).rstrip("/")
        self._token: Optional[str] = None
        self._session = requests.Session()
        self._on_unauthorized = on_unauthorized
        self._player = player

    def set_token(self, token: Optional[str]) -> None:
        """Store JWT token in memory only."""
        self._token = token

    def get_token(self) -> Optional[str]:
        return self._token

    def clear_token(self) -> None:
        """Purge JWT token from memory."""
        self._token = None

    def set_on_unauthorized(self, callback: Callable[[], None]) -> None:
        self._on_unauthorized = callback

    def set_player(self, player: Any) -> None:
        self._player = player

    # Internal HTTP Request Dispatcher
    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        timeout: float = TIMEOUT_NORMAL,
        headers: Optional[Dict[str, str]] = None
    ) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        req_headers = {"Accept": "application/json"}
        if headers:
            req_headers.update(headers)

        # Inject JWT Authorization header if available
        if self._token:
            req_headers["Authorization"] = f"Bearer {self._token}"

        try:
            resp = self._session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=req_headers,
                timeout=timeout
            )
        except requests.exceptions.Timeout as e:
            raise ApiError(408, "Request timed out. Please try again.") from e
        except requests.exceptions.ConnectionError as e:
            raise ApiError(503, "Can't reach the server. Check your network.") from e
        except requests.exceptions.RequestException as e:
            raise ApiError(500, f"Network error: {e}") from e

        # Parse JSON or Error
        try:
            body = resp.json() if resp.content else {}
        except Exception:
            body = {}

        # Handle 401 Unauthorized globally (except on login endpoint which is bad credentials)
        if resp.status_code == 401:
            is_login_call = endpoint.lstrip("/").startswith("auth/login")
            if is_login_call:
                msg = body.get("message") or "Invalid username or password"
                raise ApiError(401, msg, error_type="Unauthorized")

            self.clear_token()
            if self._player:
                try:
                    self._player.stop()
                except Exception:
                    pass
            if self._on_unauthorized:
                try:
                    self._on_unauthorized()
                except Exception as e:
                    logger.error("Error in on_unauthorized callback: %s", e)
            raise ApiError(401, "Session expired. Please log in again.", error_type="Unauthorized")

        # Handle 204 No Content
        if resp.status_code == 204:
            return None

        if 200 <= resp.status_code < 300:
            return body

        # Extract error details
        status = resp.status_code
        message = body.get("message") or body.get("error") or f"HTTP {status}"
        error_type = body.get("error") or "HttpError"
        raw_field_errors = body.get("fieldErrors")
        field_errors: Dict[str, str] = {}
        if isinstance(raw_field_errors, dict):
            field_errors = {str(k): str(v) for k, v in raw_field_errors.items()}
        elif isinstance(raw_field_errors, list):
            for item in raw_field_errors:
                if isinstance(item, dict) and "field" in item and "message" in item:
                    field_errors[item["field"]] = item["message"]

        raise ApiError(status, message, field_errors=field_errors, error_type=error_type)

    # 1. Authentication
    def signup(self, username: str, email: str, password: str) -> Dict[str, Any]:
        """POST /auth/signup -> {token, user: Me}"""
        data = self._request("POST", "auth/signup", json_data={
            "username": username,
            "email": email,
            "password": password
        })
        if "token" in data:
            self.set_token(data["token"])
        return data

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """POST /auth/login -> {token, user: Me}"""
        data = self._request("POST", "auth/login", json_data={
            "username": username,
            "password": password
        })
        if "token" in data:
            self.set_token(data["token"])
        return data

    def get_me(self) -> Dict[str, Any]:
        """GET /auth/me -> Me"""
        return self._request("GET", "auth/me")

    def change_password(self, old_password: str, new_password: str) -> None:
        """PUT /auth/password {oldPassword, newPassword} -> 204"""
        self._request("PUT", "auth/password", json_data={
            "oldPassword": old_password,
            "newPassword": new_password
        })

    # 2. For You Feed & Suggestions
    def get_feed(self, page: int = 0, size: int = 10) -> Dict[str, Any]:
        """GET /feed?page=N&size=N -> {items: MediaCard[], hasNext}"""
        return self._request("GET", "feed", params={"page": page, "size": size})

    def get_suggested_users(self) -> Dict[str, Any]:
        """GET /users/suggested -> {items: UserSummary[]}"""
        return self._request("GET", "users/suggested")

    # 3. Stories
    def get_stories(self) -> Dict[str, Any]:
        """GET /stories -> {items: StoryGroup[]}"""
        return self._request("GET", "stories")

    def mark_story_seen(self, story_id: int) -> None:
        """POST /stories/{id}/seen -> 204"""
        self._request("POST", f"stories/{story_id}/seen")

    # 4. Reels Recommendations
    def get_reels(self, size: int = 5, exclude: Optional[List[int]] = None) -> Dict[str, Any]:
        """GET /reels?size=N&exclude=1,2,3 -> {items: MediaCard[], hasNext}"""
        params: Dict[str, Any] = {"size": size}
        if exclude:
            params["exclude"] = ",".join(str(i) for i in exclude[:100])
        return self._request("GET", "reels", params=params)

    # 5. Media Interactions
    def get_media(self, media_id: int) -> Dict[str, Any]:
        """GET /media/{id} -> MediaCard"""
        return self._request("GET", f"media/{media_id}")

    def delete_media(self, media_id: int) -> None:
        """DELETE /media/{id} -> 204"""
        self._request("DELETE", f"media/{media_id}")

    def like_media(self, media_id: int) -> Dict[str, Any]:
        """POST /media/{id}/like -> {liked: true, likeCount: N}"""
        return self._request("POST", f"media/{media_id}/like")

    def unlike_media(self, media_id: int) -> Dict[str, Any]:
        """DELETE /media/{id}/like -> {liked: false, likeCount: N}"""
        return self._request("DELETE", f"media/{media_id}/like")

    def share_media(self, media_id: int) -> Dict[str, Any]:
        """POST /media/{id}/share -> {shareCount: N, shareUrl: str}"""
        return self._request("POST", f"media/{media_id}/share")

    def send_view_telemetry(
        self,
        media_id: int,
        watch_ms: int,
        duration_ms: int,
        completed: bool
    ) -> None:
        """POST /media/{id}/view {watchMs, durationMs, completed} -> 204"""
        self._request("POST", f"media/{media_id}/view", json_data={
            "watchMs": watch_ms,
            "durationMs": duration_ms,
            "completed": completed
        })

    # 6. Comments
    def get_comments(self, media_id: int, page: int = 0, size: int = 20) -> Dict[str, Any]:
        """GET /media/{id}/comments?page=N&size=N -> {items: Comment[], hasNext}"""
        return self._request("GET", f"media/{media_id}/comments", params={"page": page, "size": size})

    def add_comment(self, media_id: int, text: str) -> Dict[str, Any]:
        """POST /media/{id}/comments {text} -> 201 Comment"""
        return self._request("POST", f"media/{media_id}/comments", json_data={"text": text})

    def delete_comment(self, comment_id: int) -> None:
        """DELETE /comments/{id} -> 204"""
        self._request("DELETE", f"comments/{comment_id}")

    # 7. Users & Follows
    def get_profile(self, user_id: int) -> Dict[str, Any]:
        """GET /users/{id}/profile -> Profile"""
        return self._request("GET", f"users/{user_id}/profile")

    def get_user_posts(self, user_id: int, page: int = 0, size: int = 18) -> Dict[str, Any]:
        """GET /users/{id}/posts?page=N&size=N -> {items: GridItem[], hasNext}"""
        return self._request("GET", f"users/{user_id}/posts", params={"page": page, "size": size})

    def get_followers(self, user_id: int, page: int = 0, size: int = 20) -> Dict[str, Any]:
        """GET /users/{id}/followers?page=N&size=N -> {items: UserSummary[], hasNext}"""
        return self._request("GET", f"users/{user_id}/followers", params={"page": page, "size": size})

    def get_following(self, user_id: int, page: int = 0, size: int = 20) -> Dict[str, Any]:
        """GET /users/{id}/following?page=N&size=N -> {items: UserSummary[], hasNext}"""
        return self._request("GET", f"users/{user_id}/following", params={"page": page, "size": size})

    def follow_user(self, user_id: int) -> Dict[str, Any]:
        """POST /users/{id}/follow -> {following, requested, followerCount}"""
        return self._request("POST", f"users/{user_id}/follow")

    def unfollow_user(self, user_id: int) -> Dict[str, Any]:
        """DELETE /users/{id}/follow -> {following: false, requested: false, followerCount}"""
        return self._request("DELETE", f"users/{user_id}/follow")

    def update_profile(
        self,
        bio: Optional[str] = None,
        username: Optional[str] = None
    ) -> Dict[str, Any]:
        """PUT /users/me {bio, username} -> Me"""
        payload: Dict[str, Any] = {}
        if bio is not None:
            payload["bio"] = bio
        if username is not None:
            payload["username"] = username
        return self._request("PUT", "users/me", json_data=payload)

    def update_avatar(self, r2_key: str) -> Dict[str, Any]:
        """PUT /users/me/avatar {r2Key} -> Me"""
        return self._request("PUT", "users/me/avatar", json_data={"r2Key": r2_key})

    def update_settings(
        self,
        is_private: bool,
        notifications_enabled: bool
    ) -> Dict[str, Any]:
        """PUT /users/me/settings {isPrivate, notificationsEnabled} -> {isPrivate, notificationsEnabled}"""
        return self._request("PUT", "users/me/settings", json_data={
            "isPrivate": is_private,
            "notificationsEnabled": notifications_enabled
        })

    def get_follow_requests(self, page: int = 0, size: int = 20) -> Dict[str, Any]:
        """GET /follow-requests?page=N&size=N -> {items: UserSummary[], hasNext}"""
        return self._request("GET", "follow-requests", params={"page": page, "size": size})

    def accept_follow_request(self, user_id: int) -> None:
        """POST /follow-requests/{userId}/accept -> 204"""
        self._request("POST", f"follow-requests/{user_id}/accept")

    def decline_follow_request(self, user_id: int) -> None:
        """POST /follow-requests/{userId}/decline -> 204"""
        self._request("POST", f"follow-requests/{user_id}/decline")

    # 8. Media Uploads (Presign + Direct PUT + Confirm)
    def presign_upload(
        self,
        file_name: str,
        content_type: str,
        media_type: str,
        file_size: int
    ) -> Dict[str, Any]:
        """POST /uploads/presign {fileName, contentType, type, fileSize} -> {uploadUrl, r2Key}"""
        return self._request("POST", "uploads/presign", json_data={
            "fileName": file_name,
            "contentType": content_type,
            "type": media_type,
            "fileSize": file_size
        })

    def confirm_upload(
        self,
        r2_key: str,
        media_type: str,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        """POST /uploads/confirm {r2Key, type, caption} -> 201 MediaCard"""
        payload: Dict[str, Any] = {
            "r2Key": r2_key,
            "type": media_type
        }
        if caption is not None:
            payload["caption"] = caption
        return self._request("POST", "uploads/confirm", json_data=payload)

    def upload_file_binary(
        self,
        upload_url: str,
        file_path_or_bytes: Union[str, Path, bytes],
        content_type: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> None:
        """
        Direct HTTP PUT upload of binary payload to presigned URL (R2 or local).
        CRITICAL: Never send Authorization header to presigned upload URL!
        """
        headers = {
            "Content-Type": content_type
        }

        if isinstance(file_path_or_bytes, bytes):
            total_size = len(file_path_or_bytes)
            headers["Content-Length"] = str(total_size)
            stream_obj = io.BytesIO(file_path_or_bytes)
            wrapper = ProgressFileWrapper(stream_obj, total_size, progress_callback)
            resp = requests.put(upload_url, data=wrapper, headers=headers, timeout=TIMEOUT_UPLOAD)
        else:
            p = Path(file_path_or_bytes)
            total_size = p.stat().st_size
            headers["Content-Length"] = str(total_size)
            with open(p, "rb") as f:
                wrapper = ProgressFileWrapper(f, total_size, progress_callback)
                resp = requests.put(upload_url, data=wrapper, headers=headers, timeout=TIMEOUT_UPLOAD)

        if resp.status_code not in (200, 201, 204):
            raise ApiError(
                resp.status_code,
                f"Binary upload failed with HTTP {resp.status_code}: {resp.text}"
            )
