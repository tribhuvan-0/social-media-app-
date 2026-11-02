#!/usr/bin/env python3
"""
SocialApp REST API Integration & Functional Verification Test Runner
====================================================================
Comprehensive standalone CLI test suite verifying all API endpoints
end-to-end against a running Spring Boot backend.

Zero external dependencies - uses standard library (urllib.request, json, argparse).

Usage:
  python3 test_api.py [--base-url http://localhost:8080/api] [--verbose] [--no-color]
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# CLI Colors & Formatting
# =============================================================================

class Colors:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    @property
    def RESET(self) -> str: return "\033[0m" if self.enabled else ""
    @property
    def BOLD(self) -> str: return "\033[1m" if self.enabled else ""
    @property
    def RED(self) -> str: return "\033[31m" if self.enabled else ""
    @property
    def GREEN(self) -> str: return "\033[32m" if self.enabled else ""
    @property
    def YELLOW(self) -> str: return "\033[33m" if self.enabled else ""
    @property
    def BLUE(self) -> str: return "\033[34m" if self.enabled else ""
    @property
    def MAGENTA(self) -> str: return "\033[35m" if self.enabled else ""
    @property
    def CYAN(self) -> str: return "\033[36m" if self.enabled else ""
    @property
    def WHITE(self) -> str: return "\033[37m" if self.enabled else ""

# =============================================================================
# HTTP Client Wrapper
# =============================================================================

class ApiClient:
    def __init__(self, base_url: str, verbose: bool = False, colors: Optional[Colors] = None):
        self.base_url = base_url.rstrip("/")
        self.verbose = verbose
        self.c = colors or Colors(enabled=True)

    def request(
        self,
        method: str,
        path: str,
        token: Optional[str] = None,
        json_body: Optional[Dict[str, Any]] = None,
        raw_body: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Any, Dict[str, str]]:
        url = self.base_url + path
        if query_params:
            encoded_params = urllib.parse.urlencode({k: v for k, v in query_params.items() if v is not None})
            if encoded_params:
                url += "?" + encoded_params

        req_headers = {"User-Agent": "SocialApp-TestRunner/1.0"}
        if token:
            req_headers["Authorization"] = f"Bearer {token}"
        if headers:
            req_headers.update(headers)

        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            if "Content-Type" not in req_headers:
                req_headers["Content-Type"] = "application/json"
        elif raw_body is not None:
            data = raw_body

        if self.verbose:
            print(f"\n{self.c.CYAN}--> {method} {url}{self.c.RESET}")
            if data and len(data) < 1000:
                print(f"{self.c.YELLOW}Body: {data.decode('utf-8', errors='replace')}{self.c.RESET}")

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)

        start_time = time.time()
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                elapsed_ms = (time.time() - start_time) * 1000
                status_code = resp.status
                resp_headers = dict(resp.headers)
                raw_resp = resp.read()
                parsed_resp = None
                if raw_resp:
                    content_type = resp_headers.get("Content-Type", "")
                    if "application/json" in content_type:
                        try:
                            parsed_resp = json.loads(raw_resp.decode("utf-8"))
                        except Exception:
                            parsed_resp = raw_resp
                    else:
                        parsed_resp = raw_resp

                if self.verbose:
                    print(f"{self.c.GREEN}<-- {status_code} ({elapsed_ms:.1f}ms){self.c.RESET}")
                    if parsed_resp and not isinstance(parsed_resp, bytes):
                        print(f"{self.c.WHITE}{json.dumps(parsed_resp, indent=2)}{self.c.RESET}")

                return status_code, parsed_resp, resp_headers

        except urllib.error.HTTPError as err:
            elapsed_ms = (time.time() - start_time) * 1000
            status_code = err.code
            resp_headers = dict(err.headers)
            raw_resp = err.read()
            parsed_resp = None
            if raw_resp:
                try:
                    parsed_resp = json.loads(raw_resp.decode("utf-8"))
                except Exception:
                    parsed_resp = raw_resp.decode("utf-8", errors="replace")

            if self.verbose:
                print(f"{self.c.RED}<-- HTTP {status_code} ({elapsed_ms:.1f}ms){self.c.RESET}")
                if parsed_resp:
                    print(f"{self.c.RED}{parsed_resp}{self.c.RESET}")

            return status_code, parsed_resp, resp_headers
        except Exception as e:
            if self.verbose:
                print(f"{self.c.RED}Connection error to {url}: {e}{self.c.RESET}")
            raise

# =============================================================================
# Test Suite Runner
# =============================================================================

class TestRunner:
    def __init__(self, client: ApiClient, colors: Colors):
        self.client = client
        self.c = colors
        self.passed = 0
        self.failed = 0
        self.errors: List[Tuple[str, str]] = []

    def section(self, title: str):
        print(f"\n{self.c.BOLD}{self.c.CYAN}=== {title} ==={self.c.RESET}")

    def run_test(self, name: str, test_func):
        sys.stdout.write(f"  • {name:<55} ")
        sys.stdout.flush()
        start = time.time()
        try:
            test_func()
            elapsed_ms = (time.time() - start) * 1000
            print(f"{self.c.BOLD}{self.c.GREEN}[PASS]{self.c.RESET} ({elapsed_ms:5.1f}ms)")
            self.passed += 1
        except Exception as exc:
            elapsed_ms = (time.time() - start) * 1000
            print(f"{self.c.BOLD}{self.c.RED}[FAIL]{self.c.RESET} ({elapsed_ms:5.1f}ms)")
            self.failed += 1
            err_msg = str(exc)
            self.errors.append((name, err_msg))
            if self.client.verbose:
                import traceback
                traceback.print_exc()

# =============================================================================
# Functional Test Implementation
# =============================================================================

def run_all_tests(base_url: str, verbose: bool, no_color: bool) -> int:
    colors = Colors(enabled=not no_color and sys.stdout.isatty())
    client = ApiClient(base_url, verbose=verbose, colors=colors)
    runner = TestRunner(client, colors)

    # State carried between tests
    state: Dict[str, Any] = {
        "ts": int(time.time()),
        "user1": {},
        "user2": {},
        "media1": {},
        "story1": {},
        "reel1": {},
        "comment1": {}
    }

    print(f"{colors.BOLD}{colors.MAGENTA}")
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║                 SocialApp API Comprehensive Verification                 ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print(f"{colors.RESET}Target API: {colors.BOLD}{base_url}{colors.RESET}")

    # Verify server connectivity first
    try:
        status, _, _ = client.request("GET", "/users/suggested")
        # 401 Unauthorized is expected for unauthenticated request, indicating server is alive!
        if status not in (200, 401, 403):
            print(f"{colors.YELLOW}Warning: Probe returned unexpected status {status}{colors.RESET}")
    except Exception as e:
        print(f"\n{colors.BOLD}{colors.RED}ERROR: Unable to connect to backend at {base_url}!{colors.RESET}")
        print(f"Details: {e}")
        print(f"\nPlease ensure the backend application is running:")
        print(f"  cd backend && ./mvnw spring-boot:run")
        return 2

    # -------------------------------------------------------------------------
    # 1. Authentication Flow
    # -------------------------------------------------------------------------
    runner.section("1. Authentication & Account Management")

    u1_name = f"user1_{state['ts']}"
    u1_email = f"user1_{state['ts']}@example.com"
    u1_pass = "Password123!"

    def test_signup_user1():
        status, data, _ = client.request("POST", "/auth/signup", json_body={
            "username": u1_name,
            "email": u1_email,
            "password": u1_pass
        })
        assert status == 201, f"Expected 201 Created, got {status}: {data}"
        assert "token" in data, "Token missing in signup response"
        assert "user" in data, "User profile missing in signup response"
        assert data["user"]["username"] == u1_name, f"Expected username {u1_name}, got {data['user']['username']}"
        state["user1"] = {
            "id": data["user"]["id"],
            "username": u1_name,
            "email": u1_email,
            "password": u1_pass,
            "token": data["token"]
        }
    runner.run_test("POST /api/auth/signup (User 1)", test_signup_user1)

    def test_signup_duplicate_username():
        status, data, _ = client.request("POST", "/auth/signup", json_body={
            "username": u1_name,
            "email": f"other_{state['ts']}@example.com",
            "password": u1_pass
        })
        assert status == 409, f"Expected 409 Conflict for duplicate username, got {status}"
    runner.run_test("POST /api/auth/signup (409 Conflict validation)", test_signup_duplicate_username)

    def test_login_user1():
        status, data, _ = client.request("POST", "/auth/login", json_body={
            "username": u1_name,
            "password": u1_pass
        })
        assert status == 200, f"Expected 200 OK, got {status}: {data}"
        assert "token" in data, "Token missing in login response"
        state["user1"]["token"] = data["token"]
    runner.run_test("POST /api/auth/login (User 1)", test_login_user1)

    def test_login_invalid_password():
        status, _, _ = client.request("POST", "/auth/login", json_body={
            "username": u1_name,
            "password": "WrongPassword999!"
        })
        assert status == 401, f"Expected 401 Unauthorized, got {status}"
    runner.run_test("POST /api/auth/login (401 Bad Credentials)", test_login_invalid_password)

    def test_get_me():
        status, data, _ = client.request("GET", "/auth/me", token=state["user1"]["token"])
        assert status == 200, f"Expected 200 OK, got {status}"
        assert data["id"] == state["user1"]["id"]
        assert data["username"] == u1_name
        assert data["email"] == u1_email
        assert "isPrivate" in data
        assert "notificationsEnabled" in data
    runner.run_test("GET /api/auth/me (Current User Profile)", test_get_me)

    def test_change_password():
        new_pass = "NewPassword456!"
        status, _, _ = client.request("PUT", "/auth/password", token=state["user1"]["token"], json_body={
            "oldPassword": u1_pass,
            "newPassword": new_pass
        })
        assert status == 204, f"Expected 204 No Content, got {status}"
        state["user1"]["password"] = new_pass
    runner.run_test("PUT /api/auth/password (Change Password)", test_change_password)

    def test_login_with_new_password():
        status, data, _ = client.request("POST", "/auth/login", json_body={
            "username": u1_name,
            "password": state["user1"]["password"]
        })
        assert status == 200, f"Expected 200 OK after password change, got {status}"
        state["user1"]["token"] = data["token"]
    runner.run_test("POST /api/auth/login (Verify New Password)", test_login_with_new_password)

    u2_name = f"user2_{state['ts']}"
    u2_email = f"user2_{state['ts']}@example.com"
    u2_pass = "Password123!"

    def test_signup_user2():
        status, data, _ = client.request("POST", "/auth/signup", json_body={
            "username": u2_name,
            "email": u2_email,
            "password": u2_pass
        })
        assert status == 201, f"Expected 201 Created for user2, got {status}"
        state["user2"] = {
            "id": data["user"]["id"],
            "username": u2_name,
            "email": u2_email,
            "password": u2_pass,
            "token": data["token"]
        }
    runner.run_test("POST /api/auth/signup (User 2 for Social Graph)", test_signup_user2)

    # -------------------------------------------------------------------------
    # 2. Uploads & Local Storage Flow
    # -------------------------------------------------------------------------
    runner.section("2. Dual-Mode Storage & Upload Pipelines")

    def test_presign_image_upload():
        status, data, _ = client.request("POST", "/uploads/presign", token=state["user1"]["token"], json_body={
            "fileName": "sample_photo.jpg",
            "contentType": "image/jpeg",
            "type": "POST",
            "fileSize": 1024
        })
        assert status == 200, f"Expected 200 OK, got {status}: {data}"
        assert "uploadUrl" in data and "r2Key" in data
        assert data["r2Key"].startswith(f"POST/{state['user1']['id']}/")
        state["upload_image"] = data
    runner.run_test("POST /api/uploads/presign (Image Upload)", test_presign_image_upload)

    # Minimal valid 1x1 JPEG bytes
    jpeg_bytes = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x01,
        0x00, 0x60, 0x00, 0x60, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43, 0x00, 0x08, 0x06, 0x06,
        0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09, 0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D,
        0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12, 0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D,
        0x1A, 0x1C, 0x1C, 0x20, 0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28,
        0x37, 0x29, 0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01, 0x00, 0x01,
        0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00, 0x01, 0x05, 0x01, 0x01,
        0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x02,
        0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0xFF, 0xDA, 0x00, 0x08, 0x01,
        0x01, 0x00, 0x00, 0x3F, 0x00, 0xBF, 0x80, 0xFF, 0xD9
    ])

    def test_local_storage_put_binary():
        r2_key = state["upload_image"]["r2Key"]
        path = f"/uploads/local-storage/{r2_key}"
        status, _, _ = client.request("PUT", path, raw_body=jpeg_bytes, headers={"Content-Type": "image/jpeg"})
        assert status == 200, f"Expected 200 OK for local storage PUT, got {status}"
    runner.run_test("PUT /api/uploads/local-storage/** (Binary Upload)", test_local_storage_put_binary)

    def test_local_storage_get_binary():
        r2_key = state["upload_image"]["r2Key"]
        path = f"/uploads/local-storage/{r2_key}"
        status, data, headers = client.request("GET", path)
        assert status == 200, f"Expected 200 OK for local storage GET, got {status}"
        assert isinstance(data, bytes) and len(data) == len(jpeg_bytes)
        assert "image/jpeg" in headers.get("Content-Type", "")
    runner.run_test("GET /api/uploads/local-storage/** (Binary Serve)", test_local_storage_get_binary)

    def test_confirm_upload_post():
        r2_key = state["upload_image"]["r2Key"]
        status, data, _ = client.request("POST", "/uploads/confirm", token=state["user1"]["token"], json_body={
            "r2Key": r2_key,
            "type": "POST",
            "caption": "Sunset in Berlin! #photography #nature #travel"
        })
        assert status == 201, f"Expected 201 Created, got {status}: {data}"
        assert data["type"] == "POST"
        assert data["mediaKind"] == "IMAGE"
        assert set(data["tags"]) == {"photography", "nature", "travel"}
        assert data["user"]["id"] == state["user1"]["id"]
        state["media1"] = data
    runner.run_test("POST /api/uploads/confirm (Create Media & Extract Tags)", test_confirm_upload_post)

    def test_confirm_unauthorized_key():
        fake_key = f"POST/{state['user2']['id']}/malicious.jpg"
        status, _, _ = client.request("POST", "/uploads/confirm", token=state["user1"]["token"], json_body={
            "r2Key": fake_key,
            "type": "POST",
            "caption": "Hijack test"
        })
        assert status == 403, f"Expected 403 Forbidden for mismatched key owner, got {status}"
    runner.run_test("POST /api/uploads/confirm (403 Key Ownership Guard)", test_confirm_unauthorized_key)

    def test_presign_validation_invalid_type():
        status, _, _ = client.request("POST", "/uploads/presign", token=state["user1"]["token"], json_body={
            "fileName": "reel.jpg",
            "contentType": "image/jpeg",
            "type": "REEL",
            "fileSize": 1024
        })
        assert status == 400, f"Expected 400 Bad Request (REEL must be video/mp4), got {status}"
    runner.run_test("POST /api/uploads/presign (400 REEL Content-Type Validation)", test_presign_validation_invalid_type)

    # -------------------------------------------------------------------------
    # 3. Feed & Suggested Users
    # -------------------------------------------------------------------------
    runner.section("3. Feed & Discovery")

    def test_get_feed():
        status, data, _ = client.request("GET", "/feed", token=state["user1"]["token"], query_params={"page": 0, "size": 10})
        assert status == 200, f"Expected 200 OK, got {status}: {data}"
        assert "items" in data and "hasNext" in data
        assert isinstance(data["items"], list)
        # Post created by user1 should appear in user1's feed
        feed_ids = [m["id"] for m in data["items"]]
        assert state["media1"]["id"] in feed_ids, f"Expected media1 {state['media1']['id']} in feed"
    runner.run_test("GET /api/feed (For You Feed)", test_get_feed)

    def test_get_suggested_users():
        status, data, _ = client.request("GET", "/users/suggested", token=state["user1"]["token"])
        assert status == 200, f"Expected 200 OK, got {status}: {data}"
        assert "items" in data
        assert isinstance(data["items"], list)
    runner.run_test("GET /api/users/suggested (Suggested Creators)", test_get_suggested_users)

    # -------------------------------------------------------------------------
    # 4. Stories & Story Views
    # -------------------------------------------------------------------------
    runner.section("4. Stories & Story Views")

    def test_create_story():
        status, p_data, _ = client.request("POST", "/uploads/presign", token=state["user1"]["token"], json_body={
            "fileName": "story.jpg",
            "contentType": "image/jpeg",
            "type": "STORY",
            "fileSize": 1024
        })
        assert status == 200
        # Write binary
        client.request("PUT", f"/uploads/local-storage/{p_data['r2Key']}", raw_body=jpeg_bytes, headers={"Content-Type": "image/jpeg"})
        # Confirm
        status, c_data, _ = client.request("POST", "/uploads/confirm", token=state["user1"]["token"], json_body={
            "r2Key": p_data["r2Key"],
            "type": "STORY",
            "caption": "My Daily Story"
        })
        assert status == 201, f"Expected 201 Created for story, got {status}"
        assert c_data["type"] == "STORY"
        state["story1"] = c_data
    runner.run_test("Create Active Story Flow (Presign + PUT + Confirm)", test_create_story)

    def test_get_stories():
        status, data, _ = client.request("GET", "/stories", token=state["user1"]["token"])
        assert status == 200, f"Expected 200 OK, got {status}: {data}"
        assert "items" in data
        assert isinstance(data["items"], list)
        story_ids = []
        for group in data["items"]:
            for s in group.get("stories", []):
                story_ids.append(s["id"])
        assert state["story1"]["id"] in story_ids, f"Story {state['story1']['id']} not found in active stories feed"
    runner.run_test("GET /api/stories (Active Stories Feed)", test_get_stories)

    def test_mark_story_seen():
        story_id = state["story1"]["id"]
        status, _, _ = client.request("POST", f"/stories/{story_id}/seen", token=state["user2"]["token"])
        assert status == 204, f"Expected 204 No Content, got {status}"
    runner.run_test("POST /api/stories/{id}/seen (Track Story View)", test_mark_story_seen)

    def test_mark_story_seen_idempotent():
        story_id = state["story1"]["id"]
        status, _, _ = client.request("POST", f"/stories/{story_id}/seen", token=state["user2"]["token"])
        assert status == 204, f"Expected 204 No Content on duplicate seen, got {status}"
    runner.run_test("POST /api/stories/{id}/seen (Idempotent Repeated Call)", test_mark_story_seen_idempotent)

    # -------------------------------------------------------------------------
    # 5. Reels Recommendation Engine
    # -------------------------------------------------------------------------
    runner.section("5. Reels 3-Pool Recommendation Engine")

    def test_create_reel():
        status, p_data, _ = client.request("POST", "/uploads/presign", token=state["user1"]["token"], json_body={
            "fileName": "dance.mp4",
            "contentType": "video/mp4",
            "type": "REEL",
            "fileSize": len(jpeg_bytes)
        })
        assert status == 200
        # Write dummy binary
        client.request("PUT", f"/uploads/local-storage/{p_data['r2Key']}", raw_body=jpeg_bytes, headers={"Content-Type": "video/mp4"})
        status, c_data, _ = client.request("POST", "/uploads/confirm", token=state["user1"]["token"], json_body={
            "r2Key": p_data["r2Key"],
            "type": "REEL",
            "caption": "Viral dance challenge! #dance #music #vibes"
        })
        assert status == 201, f"Expected 201 Created for reel, got {status}"
        assert c_data["type"] == "REEL"
        state["reel1"] = c_data
    runner.run_test("Create Reel Flow (Presign + PUT + Confirm)", test_create_reel)

    def test_get_reels_recommendations():
        status, data, _ = client.request("GET", "/reels", token=state["user2"]["token"], query_params={"size": 5})
        assert status == 200, f"Expected 200 OK, got {status}: {data}"
        assert "items" in data and "hasNext" in data
        assert isinstance(data["items"], list)
        for item in data["items"]:
            assert item["type"] == "REEL"
    runner.run_test("GET /api/reels (3-Pool Recommendations)", test_get_reels_recommendations)

    def test_reels_exclude_parameter():
        reel_id = state["reel1"]["id"]
        status, data, _ = client.request("GET", "/reels", token=state["user2"]["token"], query_params={"size": 5, "exclude": str(reel_id)})
        assert status == 200, f"Expected 200 OK, got {status}"
        reel_ids = [r["id"] for r in data["items"]]
        assert reel_id not in reel_ids, f"Excluded reel {reel_id} should not appear in recommendations"
    runner.run_test("GET /api/reels?exclude=... (Candidate Exclusion)", test_reels_exclude_parameter)

    # -------------------------------------------------------------------------
    # 6. Media Interactions & Comments
    # -------------------------------------------------------------------------
    runner.section("6. Media Interactions, Telemetry & Comments")

    def test_get_media_detail():
        mid = state["media1"]["id"]
        status, data, _ = client.request("GET", f"/media/{mid}", token=state["user2"]["token"])
        assert status == 200, f"Expected 200 OK, got {status}"
        assert data["id"] == mid
        assert data["likedByMe"] is False
    runner.run_test("GET /api/media/{id} (Media Detail)", test_get_media_detail)

    def test_like_media():
        mid = state["media1"]["id"]
        status, data, _ = client.request("POST", f"/media/{mid}/like", token=state["user2"]["token"])
        assert status == 200, f"Expected 200 OK, got {status}"
        assert data["liked"] is True
        assert data["likeCount"] >= 1
    runner.run_test("POST /api/media/{id}/like (Like Media)", test_like_media)

    def test_like_media_idempotent():
        mid = state["media1"]["id"]
        status, data, _ = client.request("POST", f"/media/{mid}/like", token=state["user2"]["token"])
        assert status == 200, f"Expected 200 OK on duplicate like, got {status}"
        assert data["liked"] is True
    runner.run_test("POST /api/media/{id}/like (Idempotent Repeated Like)", test_like_media_idempotent)

    def test_unlike_media():
        mid = state["media1"]["id"]
        status, data, _ = client.request("DELETE", f"/media/{mid}/like", token=state["user2"]["token"])
        assert status == 200, f"Expected 200 OK, got {status}"
        assert data["liked"] is False
    runner.run_test("DELETE /api/media/{id}/like (Unlike Media)", test_unlike_media)

    def test_share_media():
        mid = state["media1"]["id"]
        status, data, _ = client.request("POST", f"/media/{mid}/share", token=state["user2"]["token"])
        assert status == 200, f"Expected 200 OK, got {status}"
        assert data["shareCount"] >= 1
        assert f"/m/{mid}" in data["shareUrl"]
    runner.run_test("POST /api/media/{id}/share (Atomic Counter & Share URL)", test_share_media)

    def test_view_telemetry():
        mid = state["media1"]["id"]
        status, _, _ = client.request("POST", f"/media/{mid}/view", token=state["user2"]["token"], json_body={
            "watchMs": 5500,
            "durationMs": 10000,
            "completed": False
        })
        assert status == 204, f"Expected 204 No Content, got {status}"
    runner.run_test("POST /api/media/{id}/view (Watch Telemetry Event)", test_view_telemetry)

    def test_add_comment():
        mid = state["media1"]["id"]
        status, data, _ = client.request("POST", f"/media/{mid}/comments", token=state["user2"]["token"], json_body={
            "text": "Incredible lighting and composition! Love this shot."
        })
        assert status == 201, f"Expected 201 Created, got {status}"
        assert "id" in data
        assert data["text"] == "Incredible lighting and composition! Love this shot."
        assert data["user"]["id"] == state["user2"]["id"]
        state["comment1"] = data
    runner.run_test("POST /api/media/{id}/comments (Add Comment)", test_add_comment)

    def test_list_comments():
        mid = state["media1"]["id"]
        status, data, _ = client.request("GET", f"/media/{mid}/comments", token=state["user1"]["token"], query_params={"page": 0, "size": 20})
        assert status == 200, f"Expected 200 OK, got {status}"
        assert "items" in data and "hasNext" in data
        comment_ids = [c["id"] for c in data["items"]]
        assert state["comment1"]["id"] in comment_ids, "Added comment not found in comments list"
    runner.run_test("GET /api/media/{id}/comments (List Comments)", test_list_comments)

    def test_delete_comment():
        cid = state["comment1"]["id"]
        status, _, _ = client.request("DELETE", f"/comments/{cid}", token=state["user2"]["token"])
        assert status == 204, f"Expected 204 No Content on delete comment, got {status}"
    runner.run_test("DELETE /api/comments/{id} (Delete Comment Author)", test_delete_comment)

    # -------------------------------------------------------------------------
    # 7. Users, Social Graph & Follow Requests
    # -------------------------------------------------------------------------
    runner.section("7. Social Graph, Profile Management & Follow Requests")

    def test_get_user_profile():
        u2_id = state["user2"]["id"]
        status, data, _ = client.request("GET", f"/users/{u2_id}/profile", token=state["user1"]["token"])
        assert status == 200, f"Expected 200 OK, got {status}"
        assert data["id"] == u2_id
        assert data["canView"] is True
    runner.run_test("GET /api/users/{id}/profile (User Profile)", test_get_user_profile)

    def test_get_user_posts_grid():
        u1_id = state["user1"]["id"]
        status, data, _ = client.request("GET", f"/users/{u1_id}/posts", token=state["user2"]["token"], query_params={"page": 0, "size": 18})
        assert status == 200, f"Expected 200 OK, got {status}"
        assert "items" in data and "hasNext" in data
        assert isinstance(data["items"], list)
    runner.run_test("GET /api/users/{id}/posts (3-Column Media Grid)", test_get_user_posts_grid)

    def test_follow_public_user():
        u1_id = state["user1"]["id"]
        status, data, _ = client.request("POST", f"/users/{u1_id}/follow", token=state["user2"]["token"])
        assert status == 200, f"Expected 200 OK, got {status}"
        assert data["following"] is True
        assert data["requested"] is False
    runner.run_test("POST /api/users/{id}/follow (Follow Public Account)", test_follow_public_user)

    def test_list_following():
        u2_id = state["user2"]["id"]
        status, data, _ = client.request("GET", f"/users/{u2_id}/following", token=state["user2"]["token"])
        assert status == 200, f"Expected 200 OK, got {status}"
        following_ids = [u["id"] for u in data["items"]]
        assert state["user1"]["id"] in following_ids
    runner.run_test("GET /api/users/{id}/following (Following List)", test_list_following)

    def test_list_followers():
        u1_id = state["user1"]["id"]
        status, data, _ = client.request("GET", f"/users/{u1_id}/followers", token=state["user1"]["token"])
        assert status == 200, f"Expected 200 OK, got {status}"
        follower_ids = [u["id"] for u in data["items"]]
        assert state["user2"]["id"] in follower_ids
    runner.run_test("GET /api/users/{id}/followers (Followers List)", test_list_followers)

    def test_unfollow_user():
        u1_id = state["user1"]["id"]
        status, data, _ = client.request("DELETE", f"/users/{u1_id}/follow", token=state["user2"]["token"])
        assert status == 200, f"Expected 200 OK, got {status}"
        assert data["following"] is False
        assert data["requested"] is False
    runner.run_test("DELETE /api/users/{id}/follow (Unfollow User)", test_unfollow_user)

    def test_private_account_and_follow_request():
        # User 2 switches to private
        status, data, _ = client.request("PUT", "/users/me/settings", token=state["user2"]["token"], json_body={
            "isPrivate": True,
            "notificationsEnabled": True
        })
        assert status == 200 and data["isPrivate"] is True

        # User 1 sends follow to private User 2
        u2_id = state["user2"]["id"]
        status, f_data, _ = client.request("POST", f"/users/{u2_id}/follow", token=state["user1"]["token"])
        assert status == 200
        assert f_data["following"] is False
        assert f_data["requested"] is True
    runner.run_test("Follow Private Account (Creates Follow Request)", test_private_account_and_follow_request)

    def test_list_and_accept_follow_request():
        # User 2 checks follow requests
        status, data, _ = client.request("GET", "/follow-requests", token=state["user2"]["token"])
        assert status == 200
        req_ids = [u["id"] for u in data["items"]]
        assert state["user1"]["id"] in req_ids

        # User 2 accepts request
        u1_id = state["user1"]["id"]
        status, _, _ = client.request("POST", f"/follow-requests/{u1_id}/accept", token=state["user2"]["token"])
        assert status == 204

        # Verify User 1 now follows User 2
        u2_id = state["user2"]["id"]
        status, p_data, _ = client.request("GET", f"/users/{u2_id}/profile", token=state["user1"]["token"])
        assert status == 200
        assert p_data["followedByMe"] is True
        assert p_data["canView"] is True
    runner.run_test("Accept Follow Request Flow (GET + POST accept)", test_list_and_accept_follow_request)

    def test_decline_follow_request_flow():
        # User 1 unfollows User 2
        u2_id = state["user2"]["id"]
        client.request("DELETE", f"/users/{u2_id}/follow", token=state["user1"]["token"])

        # User 1 requests again
        client.request("POST", f"/users/{u2_id}/follow", token=state["user1"]["token"])

        # User 2 declines request
        u1_id = state["user1"]["id"]
        status, _, _ = client.request("POST", f"/follow-requests/{u1_id}/decline", token=state["user2"]["token"])
        assert status == 204

        # Request should now be absent
        status, data, _ = client.request("GET", "/follow-requests", token=state["user2"]["token"])
        req_ids = [u["id"] for u in data["items"]]
        assert u1_id not in req_ids
    runner.run_test("Decline Follow Request Flow (POST decline)", test_decline_follow_request_flow)

    def test_update_profile():
        new_bio = "Building high-performance social backend systems."
        status, data, _ = client.request("PUT", "/users/me", token=state["user1"]["token"], json_body={
            "bio": new_bio
        })
        assert status == 200, f"Expected 200 OK, got {status}"
        assert data["bio"] == new_bio
    runner.run_test("PUT /api/users/me (Update Bio)", test_update_profile)

    def test_update_settings():
        status, data, _ = client.request("PUT", "/users/me/settings", token=state["user1"]["token"], json_body={
            "isPrivate": False,
            "notificationsEnabled": False
        })
        assert status == 200, f"Expected 200 OK, got {status}"
        assert data["isPrivate"] is False
        assert data["notificationsEnabled"] is False
    runner.run_test("PUT /api/users/me/settings (Update Settings)", test_update_settings)

    def test_delete_media_cleanup():
        mid = state["media1"]["id"]
        status, _, _ = client.request("DELETE", f"/media/{mid}", token=state["user1"]["token"])
        assert status == 204, f"Expected 204 No Content on delete media, got {status}"

        # Subsequent fetch must yield 404 Not Found
        status, _, _ = client.request("GET", f"/media/{mid}", token=state["user1"]["token"])
        assert status == 404, f"Expected 404 Not Found after deletion, got {status}"
    runner.run_test("DELETE /api/media/{id} (Owner Media Deletion & 404 Verification)", test_delete_media_cleanup)

    # -------------------------------------------------------------------------
    # Final Summary
    # -------------------------------------------------------------------------
    total_tests = runner.passed + runner.failed
    print(f"\n{colors.BOLD}══════════════════════════════════════════════════════════════════════════{colors.RESET}")
    print(f"{colors.BOLD}SocialApp REST API Integration Verification Summary{colors.RESET}")
    print(f"══════════════════════════════════════════════════════════════════════════")
    print(f"  Total Functional Tests: {total_tests}")
    print(f"  Passed:                 {colors.GREEN}{runner.passed}{colors.RESET}")
    print(f"  Failed:                 {colors.RED if runner.failed > 0 else colors.GREEN}{runner.failed}{colors.RESET}")

    if runner.failed > 0:
        print(f"\n{colors.BOLD}{colors.RED}Failed Tests Detail:{colors.RESET}")
        for name, err in runner.errors:
            print(f"  • {name}: {err}")
        print(f"\n{colors.BOLD}{colors.RED}VERIFICATION FAILED{colors.RESET}")
        return 1
    else:
        print(f"\n{colors.BOLD}{colors.GREEN}✓ ALL API FUNCTIONAL VERIFICATION TESTS PASSED SUCCESSFULLY!{colors.RESET}")
        return 0

# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="SocialApp REST API Integration & Functional Verification Suite"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8080/api",
        help="Base URL of running SocialApp REST API (default: http://localhost:8080/api)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print verbose HTTP request payloads and responses"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colored output"
    )

    args = parser.parse_args()
    exit_code = run_all_tests(base_url=args.base_url, verbose=args.verbose, no_color=args.no_color)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
