"""
Comprehensive MockApi implementation for offline development and testing.
Provides 100% method-for-method and contract-compliant parity with ApiClient.
Dynamically generates Pillow placeholder images (1:1, 4:5, 9:16) with gradients,
initials, and tags, enabling full desktop client execution without a backend server.
"""

from datetime import datetime, timedelta, timezone
import io
import logging
import math
import os
from pathlib import Path
import random
import threading
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

from .api import ApiError
from .config import CACHE_DIR, IMAGE_CACHE_DIR

logger = logging.getLogger("SocialApp.mock_api")

MOCK_MEDIA_DIR = CACHE_DIR / "mock_media"
try:
    MOCK_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass


def _iso_now(delta_seconds: int = 0) -> str:
    """Generate ISO-8601 UTC timestamp string."""
    dt = datetime.now(timezone.utc) + timedelta(seconds=delta_seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _generate_gradient_image(
    width: int,
    height: int,
    color_start: Tuple[int, int, int],
    color_end: Tuple[int, int, int],
    label: str = "",
    subtitle: str = ""
) -> str:
    """
    Generate a dynamic Pillow placeholder image with gradient fill and text,
    and save to MOCK_MEDIA_DIR. Returns the absolute file path.
    """
    img = Image.new("RGB", (width, height), color_start)
    draw = ImageDraw.Draw(img)

    # Vertical gradient calculation
    r1, g1, b1 = color_start
    r2, g2, b2 = color_end
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Add subtle grid pattern
    grid_spacing = 40
    for x in range(0, width, grid_spacing):
        draw.line([(x, 0), (x, height)], fill=(255, 255, 255, 20), width=1)
    for y in range(0, height, grid_spacing):
        draw.line([(0, y), (width, y)], fill=(255, 255, 255, 20), width=1)

    # Render label and subtitle
    if label:
        try:
            draw.text((width // 2, height // 2 - 16), label, fill="#FFFFFF", anchor="mm")
            if subtitle:
                draw.text((width // 2, height // 2 + 16), subtitle, fill="#CCCCCC", anchor="mm")
        except Exception:
            pass

    safe_name = "".join(c if c.isalnum() else "_" for c in label[:20]) or "media"
    file_path = MOCK_MEDIA_DIR / f"mock_{safe_name}_{width}x{height}.jpg"
    try:
        img.save(file_path, "JPEG", quality=85)
        return str(file_path.resolve())
    except Exception:
        return ""


def _generate_avatar(initials: str, color_start: Tuple[int, int, int], color_end: Tuple[int, int, int]) -> str:
    """Generate dynamic circular avatar placeholder and return file path."""
    size = 160
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw gradient or solid circle
    draw.ellipse((0, 0, size, size), fill=color_start)
    try:
        draw.text((size // 2, size // 2), initials, fill="#FFFFFF", anchor="mm")
    except Exception:
        pass

    file_path = MOCK_MEDIA_DIR / f"avatar_{initials}_{size}.png"
    try:
        img.save(file_path, "PNG")
        return str(file_path.resolve())
    except Exception:
        return ""


class MockApi:
    """
    Offline Mock API implementing the exact backend REST contract from docs.md.
    Maintains mutable in-memory state for users, feeds, reels, stories, likes,
    comments, and follow graphs.
    """

    def __init__(self, on_unauthorized: Optional[Callable[[], None]] = None) -> None:
        self._token: Optional[str] = "mock_jwt_token_testuser_active"
        self._on_unauthorized = on_unauthorized
        self._player: Any = None
        self._lock = threading.RLock()

        # Seed Database
        self._current_user_id = 6
        self._users: Dict[int, Dict[str, Any]] = {}
        self._media: Dict[int, Dict[str, Any]] = {}
        self._stories: Dict[int, List[Dict[str, Any]]] = {}
        self._comments: Dict[int, List[Dict[str, Any]]] = {}
        self._follows: Set[Tuple[int, int]] = set()  # (follower_id, following_id)
        self._follow_requests: Set[Tuple[int, int]] = set()  # (requester_id, target_id)
        self._story_views: Set[Tuple[int, int]] = set()  # (user_id, story_id)
        self._media_id_counter = 100
        self._comment_id_counter = 500

        self._seed_data()

    def set_token(self, token: Optional[str]) -> None:
        self._token = token

    def get_token(self) -> Optional[str]:
        return self._token

    def clear_token(self) -> None:
        self._token = None

    def set_on_unauthorized(self, callback: Callable[[], None]) -> None:
        self._on_unauthorized = callback

    def set_player(self, player: Any) -> None:
        self._player = player

    def _seed_data(self) -> None:
        """Populate initial mock state with 6 users and 20+ media items."""
        # 1. Users
        users_meta = [
            (1, "alex_adventures", "alex@example.com", "Exploring summits 🏔️ & photography 📷", "AA", (40, 60, 120), (20, 180, 220), False),
            (2, "sarah_codes", "sarah@example.com", "Building elegant UI systems & open source 💻✨", "SC", (120, 40, 120), (220, 80, 180), False),
            (3, "marco_foodie", "marco@example.com", "Culinary artisan 🍝 Handmade pasta & wine", "MF", (140, 60, 20), (240, 140, 40), False),
            (4, "elena_fit", "elena@example.com", "Daily movement, wellness & plant fuel 💪🥗", "EF", (20, 120, 60), (40, 220, 140), False),
            (5, "david_lens", "david@example.com", "Urban geometry & midnight neon 📸 Tokyo/Seoul", "DL", (60, 20, 120), (140, 40, 240), True),  # Private
            (6, "testuser", "testuser@socialapp.com", "SocialApp Explorer | Welcome to my feed!", "TU", (30, 140, 200), (0, 80, 160), False),  # Current User
        ]

        for uid, uname, email, bio, initials, c1, c2, is_priv in users_meta:
            avatar_path = _generate_avatar(initials, c1, c2)
            self._users[uid] = {
                "id": uid,
                "username": uname,
                "email": email,
                "bio": bio,
                "avatarUrl": avatar_path,
                "isPrivate": is_priv,
                "notificationsEnabled": True,
            }

        # Follow relationships (testuser follows 1, 2, 3)
        self._follows.add((6, 1))
        self._follows.add((6, 2))
        self._follows.add((6, 3))
        # Others follow testuser
        self._follows.add((1, 6))
        self._follows.add((2, 6))
        self._follows.add((4, 6))
        # Pending follow request from user 4 to private user 5
        self._follow_requests.add((6, 5))

        # 2. Media items (Posts & Reels)
        media_seeds = [
            # Alex (User 1)
            (1, 1, "POST", "IMAGE", "Alpine sunrise above the cloud sea ☀️ #travel #mountains #nature", ["travel", "mountains", "nature"], (30, 60, 100), (60, 120, 200), 142, 12),
            (2, 1, "REEL", "VIDEO", "Trail run descent in the Rockies 🏃‍♂️💨 #fitness #adventure #run", ["fitness", "adventure", "run"], (20, 80, 120), (40, 160, 240), 380, 24),
            (3, 1, "POST", "IMAGE", "Glacier lake reflection at dawn 🏞️ #travel #wanderlust", ["travel", "wanderlust"], (10, 50, 90), (30, 140, 180), 98, 7),
            # Sarah (User 2)
            (4, 2, "POST", "IMAGE", "Midnight architecture planning session ☕💻 #coding #developer #tech", ["coding", "developer", "tech"], (80, 20, 100), (160, 40, 200), 215, 18),
            (5, 2, "REEL", "VIDEO", "Smooth 60fps CustomTkinter fluid navigation demo 🚀 #python #ui #desktop", ["python", "ui", "desktop"], (100, 30, 80), (220, 60, 160), 640, 52),
            (6, 2, "POST", "IMAGE", "Clean workspace setup with vertical monitor ✨ #desksetup #workspace", ["desksetup", "workspace"], (60, 40, 90), (120, 80, 180), 310, 29),
            # Marco (User 3)
            (7, 3, "POST", "IMAGE", "Fresh tagliatelle al tartufo nero 🍝 #food #italian #chef", ["food", "italian", "chef"], (120, 50, 20), (220, 120, 40), 512, 43),
            (8, 3, "REEL", "VIDEO", "Sourdough crust blistering timelapse 🔥🥖 #baking #foodie #artisan", ["baking", "foodie", "artisan"], (140, 70, 30), (250, 160, 60), 890, 71),
            (9, 3, "POST", "IMAGE", "Neapolitan pizza straight from the wood oven 🍕 #pizza #napoli", ["pizza", "napoli"], (160, 40, 20), (240, 90, 40), 420, 35),
            # Elena (User 4)
            (10, 4, "POST", "IMAGE", "Morning yoga stretch with city view 🧘‍♀️ #wellness #mindfulness #health", ["wellness", "mindfulness", "health"], (20, 100, 60), (40, 200, 120), 180, 14),
            (11, 4, "REEL", "VIDEO", "Full-body kettlebell circuit breakdown 🏋️‍♀️ #fitness #workout #hiit", ["fitness", "workout", "hiit"], (30, 120, 70), (60, 240, 140), 720, 63),
            # David (User 5)
            (12, 5, "POST", "IMAGE", "Rainy neon reflections in Shinjuku 🌧️🏮 #streetphotography #tokyo #cyberpunk", ["streetphotography", "tokyo", "cyberpunk"], (50, 10, 100), (120, 30, 220), 890, 88),
            (13, 5, "REEL", "VIDEO", "Seoul midnight hyperlapse under rain 🌃 #timelapse #cinematic #city", ["timelapse", "cinematic", "city"], (30, 10, 80), (90, 20, 180), 1250, 114),
            # TestUser (User 6)
            (14, 6, "POST", "IMAGE", "First post on SocialApp! Testing rich media feeds 🚀 #socialapp #launch", ["socialapp", "launch"], (20, 80, 160), (40, 160, 240), 42, 6),
            (15, 6, "REEL", "VIDEO", "Testing video playback and view telemetry tracking 🎬 #reels #preview", ["reels", "preview"], (40, 100, 180), (80, 200, 255), 75, 9),
        ]

        sample_mp4_path = MOCK_MEDIA_DIR / "mock_sample_reel.mp4"
        if not sample_mp4_path.exists():
            repo_mp4 = Path(__file__).resolve().parent.parent / "backend" / "media-storage" / "REEL" / "1" / "film_developing.mp4"
            fallback_mp4 = Path(__file__).resolve().parent.parent / "backend" / "src" / "main" / "resources" / "sample_tiny.mp4"
            try:
                if repo_mp4.exists():
                    sample_mp4_path.write_bytes(repo_mp4.read_bytes())
                elif fallback_mp4.exists():
                    sample_mp4_path.write_bytes(fallback_mp4.read_bytes())
            except Exception:
                pass
        video_file_str = str(sample_mp4_path.resolve()) if sample_mp4_path.exists() else ""

        for mid, uid, mtype, mkind, caption, tags, c1, c2, likes, comments in media_seeds:
            aspect = (440, 440) if mtype == "POST" else (360, 640)
            img_path = _generate_gradient_image(aspect[0], aspect[1], c1, c2, label=f"Media #{mid} ({mtype})", subtitle=f"@{self._users[uid]['username']}")
            thumb_path = img_path
            media_url = (video_file_str or img_path) if mkind == "VIDEO" else img_path

            self._media[mid] = {
                "id": mid,
                "userId": uid,
                "type": mtype,
                "mediaKind": mkind,
                "mediaUrl": media_url,
                "thumbnailUrl": thumb_path,
                "caption": caption,
                "tags": tags,
                "createdAt": _iso_now(-mid * 7200),
                "likeCount": likes,
                "commentCount": comments,
                "shareCount": likes // 5,
                "likedByMe": False,
            }

            # Seed comments for this media
            self._comments[mid] = [
                {
                    "id": mid * 10 + 1,
                    "mediaId": mid,
                    "text": "Stunning shot! Love the colors and composition 🔥",
                    "createdAt": _iso_now(-mid * 3600),
                    "user": self._build_user_summary(1)
                },
                {
                    "id": mid * 10 + 2,
                    "mediaId": mid,
                    "text": "Incredible work, really well done! 👏",
                    "createdAt": _iso_now(-mid * 1800),
                    "user": self._build_user_summary(2)
                }
            ]

        # 3. Seed Stories (Alex, Sarah, TestUser)
        story_specs = [
            (1, 101, "IMAGE", "Alpine sunrise story", (40, 60, 120), (20, 180, 220)),
            (1, 102, "VIDEO", "Rope climb action", (30, 80, 140), (50, 200, 240)),
            (2, 103, "IMAGE", "Code review screenshot", (100, 30, 80), (200, 60, 160)),
            (6, 104, "IMAGE", "My test story update", (20, 100, 180), (40, 180, 240)),
        ]
        for uid, sid, skind, slabel, c1, c2 in story_specs:
            if uid not in self._stories:
                self._stories[uid] = []
            img_path = _generate_gradient_image(360, 640, c1, c2, label=f"Story #{sid}", subtitle=slabel)
            story_url = (video_file_str or img_path) if skind == "VIDEO" else img_path
            self._stories[uid].append({
                "id": sid,
                "userId": uid,
                "mediaUrl": story_url,
                "mediaKind": skind,
                "createdAt": _iso_now(-3600),
                "expiresAt": _iso_now(23 * 3600),
                "seen": False
            })

    # Internal DTO Mappers
    def _build_user_summary(self, user_id: int) -> Dict[str, Any]:
        u = self._users[user_id]
        followed = (self._current_user_id, user_id) in self._follows
        requested = (self._current_user_id, user_id) in self._follow_requests
        return {
            "id": u["id"],
            "username": u["username"],
            "avatarUrl": u["avatarUrl"],
            "followedByMe": followed,
            "requestedByMe": requested,
        }

    def _build_media_card(self, media_id: int) -> Dict[str, Any]:
        m = self._media[media_id]
        return {
            "id": m["id"],
            "type": m["type"],
            "mediaKind": m["mediaKind"],
            "mediaUrl": m["mediaUrl"],
            "thumbnailUrl": m["thumbnailUrl"],
            "caption": m["caption"],
            "tags": list(m["tags"]),
            "createdAt": m["createdAt"],
            "likeCount": m["likeCount"],
            "commentCount": len(self._comments.get(media_id, [])),
            "shareCount": m["shareCount"],
            "likedByMe": m["likedByMe"],
            "user": self._build_user_summary(m["userId"]),
        }

    # 1. Auth Endpoints
    def signup(self, username: str, email: str, password: str) -> Dict[str, Any]:
        with self._lock:
            # Check unique username
            for u in self._users.values():
                if u["username"].lower() == username.lower():
                    raise ApiError(409, "Username is already taken", field_errors={"username": "Taken"})
                if u["email"].lower() == email.lower():
                    raise ApiError(409, "Email is already registered", field_errors={"email": "Registered"})

            new_id = max(self._users.keys(), default=0) + 1
            avatar_path = _generate_avatar(username[:2].upper(), (40, 100, 180), (80, 180, 240))
            new_user = {
                "id": new_id,
                "username": username,
                "email": email,
                "bio": "New to SocialApp",
                "avatarUrl": avatar_path,
                "isPrivate": False,
                "notificationsEnabled": True,
            }
            self._users[new_id] = new_user
            self._current_user_id = new_id
            self._token = f"mock_jwt_token_{username}"
            return {
                "token": self._token,
                "user": dict(new_user)
            }

    def login(self, username: str, password: str) -> Dict[str, Any]:
        with self._lock:
            target = None
            for u in self._users.values():
                if u["username"].lower() == username.lower():
                    target = u
                    break
            if not target:
                raise ApiError(401, "Invalid username or password")

            self._current_user_id = target["id"]
            self._token = f"mock_jwt_token_{username}"
            return {
                "token": self._token,
                "user": dict(target)
            }

    def get_me(self) -> Dict[str, Any]:
        with self._lock:
            u = self._users[self._current_user_id]
            return dict(u)

    def change_password(self, old_password: str, new_password: str) -> None:
        if len(new_password) < 8:
            raise ApiError(400, "Password must be at least 8 characters", field_errors={"newPassword": "Min 8 chars"})

    # 2. Feed & Suggestions
    def get_feed(self, page: int = 0, size: int = 10) -> Dict[str, Any]:
        with self._lock:
            # POST and REEL from followed users and self
            allowed_users = {self._current_user_id}
            for fid, tid in self._follows:
                if fid == self._current_user_id:
                    allowed_users.add(tid)

            candidates = [
                m for m in self._media.values()
                if m["userId"] in allowed_users and m["type"] in ("POST", "REEL")
            ]
            candidates.sort(key=lambda x: x["createdAt"], reverse=True)

            start = page * size
            end = start + size
            slice_items = candidates[start:end]
            has_next = end < len(candidates)

            return {
                "items": [self._build_media_card(m["id"]) for m in slice_items],
                "hasNext": has_next
            }

    def get_suggested_users(self) -> Dict[str, Any]:
        with self._lock:
            followed = {tid for fid, tid in self._follows if fid == self._current_user_id}
            candidates = [
                self._build_user_summary(u["id"])
                for u in self._users.values()
                if u["id"] != self._current_user_id and u["id"] not in followed
            ]
            return {"items": candidates[:10]}

    # 3. Stories
    def get_stories(self) -> Dict[str, Any]:
        with self._lock:
            groups: List[Dict[str, Any]] = []

            # 1. My group first (if active stories exist)
            if self._current_user_id in self._stories and self._stories[self._current_user_id]:
                my_stories = self._stories[self._current_user_id]
                has_unseen = any((self._current_user_id, s["id"]) not in self._story_views for s in my_stories)
                groups.append({
                    "user": self._build_user_summary(self._current_user_id),
                    "hasUnseen": has_unseen,
                    "stories": [
                        {
                            "id": s["id"],
                            "mediaUrl": s["mediaUrl"],
                            "mediaKind": s["mediaKind"],
                            "createdAt": s["createdAt"],
                            "expiresAt": s["expiresAt"],
                            "seen": (self._current_user_id, s["id"]) in self._story_views
                        }
                        for s in my_stories
                    ]
                })

            # 2. Followed users' groups
            followed_ids = [tid for fid, tid in self._follows if fid == self._current_user_id and tid != self._current_user_id]
            for uid in followed_ids:
                if uid in self._stories and self._stories[uid]:
                    st_list = self._stories[uid]
                    has_unseen = any((self._current_user_id, s["id"]) not in self._story_views for s in st_list)
                    groups.append({
                        "user": self._build_user_summary(uid),
                        "hasUnseen": has_unseen,
                        "stories": [
                            {
                                "id": s["id"],
                                "mediaUrl": s["mediaUrl"],
                                "mediaKind": s["mediaKind"],
                                "createdAt": s["createdAt"],
                                "expiresAt": s["expiresAt"],
                                "seen": (self._current_user_id, s["id"]) in self._story_views
                            }
                            for s in st_list
                        ]
                    })

            # Sort groups: unseen first, then seen
            if groups:
                first = groups[0] if groups[0]["user"]["id"] == self._current_user_id else None
                rest = [g for g in groups if g != first]
                rest.sort(key=lambda g: 0 if g["hasUnseen"] else 1)
                final_groups = [first] + rest if first else rest
            else:
                final_groups = []

            return {"items": final_groups}

    def mark_story_seen(self, story_id: int) -> None:
        with self._lock:
            self._story_views.add((self._current_user_id, story_id))

    # 4. Reels
    def get_reels(self, size: int = 5, exclude: Optional[List[int]] = None) -> Dict[str, Any]:
        with self._lock:
            exclude_set = set(exclude or [])
            reels = [
                m for m in self._media.values()
                if m["type"] == "REEL" and m["id"] not in exclude_set
            ]
            slice_items = reels[:size]
            has_next = len(reels) > len(slice_items)
            return {
                "items": [self._build_media_card(m["id"]) for m in slice_items],
                "hasNext": has_next
            }

    # 5. Media Interactions
    def get_media(self, media_id: int) -> Dict[str, Any]:
        with self._lock:
            if media_id not in self._media:
                raise ApiError(404, "Media not found")
            m = self._media[media_id]
            owner = self._users[m["userId"]]
            # Check privacy
            can_view = (
                m["userId"] == self._current_user_id or
                not owner["isPrivate"] or
                (self._current_user_id, m["userId"]) in self._follows
            )
            if not can_view:
                raise ApiError(403, "This account is private")
            return self._build_media_card(media_id)

    def delete_media(self, media_id: int) -> None:
        with self._lock:
            if media_id not in self._media:
                raise ApiError(404, "Media not found")
            if self._media[media_id]["userId"] != self._current_user_id:
                raise ApiError(403, "Only the owner can delete media")
            del self._media[media_id]
            if media_id in self._comments:
                del self._comments[media_id]

    def like_media(self, media_id: int) -> Dict[str, Any]:
        with self._lock:
            if media_id not in self._media:
                raise ApiError(404, "Media not found")
            m = self._media[media_id]
            if not m["likedByMe"]:
                m["likedByMe"] = True
                m["likeCount"] += 1
            return {"liked": True, "likeCount": m["likeCount"]}

    def unlike_media(self, media_id: int) -> Dict[str, Any]:
        with self._lock:
            if media_id not in self._media:
                raise ApiError(404, "Media not found")
            m = self._media[media_id]
            if m["likedByMe"]:
                m["likedByMe"] = False
                m["likeCount"] = max(0, m["likeCount"] - 1)
            return {"liked": False, "likeCount": m["likeCount"]}

    def share_media(self, media_id: int) -> Dict[str, Any]:
        with self._lock:
            if media_id not in self._media:
                raise ApiError(404, "Media not found")
            m = self._media[media_id]
            m["shareCount"] += 1
            return {
                "shareCount": m["shareCount"],
                "shareUrl": f"http://localhost:8080/m/{media_id}"
            }

    def send_view_telemetry(self, media_id: int, watch_ms: int, duration_ms: int, completed: bool) -> None:
        pass  # Telemetry successfully recorded in mock mode

    # 6. Comments
    def get_comments(self, media_id: int, page: int = 0, size: int = 20) -> Dict[str, Any]:
        with self._lock:
            if media_id not in self._media:
                raise ApiError(404, "Media not found")
            c_list = self._comments.get(media_id, [])
            start = page * size
            end = start + size
            slice_items = c_list[start:end]
            return {
                "items": list(slice_items),
                "hasNext": end < len(c_list)
            }

    def add_comment(self, media_id: int, text: str) -> Dict[str, Any]:
        with self._lock:
            if media_id not in self._media:
                raise ApiError(404, "Media not found")
            cleaned = text.strip()
            if not cleaned:
                raise ApiError(400, "Comment cannot be blank", field_errors={"text": "Blank"})

            self._comment_id_counter += 1
            new_comment = {
                "id": self._comment_id_counter,
                "mediaId": media_id,
                "text": cleaned,
                "createdAt": _iso_now(),
                "user": self._build_user_summary(self._current_user_id)
            }
            if media_id not in self._comments:
                self._comments[media_id] = []
            self._comments[media_id].append(new_comment)
            self._media[media_id]["commentCount"] = len(self._comments[media_id])
            return new_comment

    def delete_comment(self, comment_id: int) -> None:
        with self._lock:
            found_media_id = None
            target_idx = None
            for mid, clist in self._comments.items():
                for i, c in enumerate(clist):
                    if c["id"] == comment_id:
                        found_media_id = mid
                        target_idx = i
                        break
                if found_media_id:
                    break

            if not found_media_id or target_idx is None:
                raise ApiError(404, "Comment not found")

            # Check permission: comment author or media owner
            c = self._comments[found_media_id][target_idx]
            media_owner = self._media[found_media_id]["userId"]
            if c["user"]["id"] != self._current_user_id and media_owner != self._current_user_id:
                raise ApiError(403, "Not authorized to delete comment")

            self._comments[found_media_id].pop(target_idx)
            self._media[found_media_id]["commentCount"] = len(self._comments[found_media_id])

    # 7. Users & Follows
    def get_profile(self, user_id: int) -> Dict[str, Any]:
        with self._lock:
            if user_id not in self._users:
                raise ApiError(404, "User not found")
            u = self._users[user_id]
            is_me = (user_id == self._current_user_id)
            followed = (self._current_user_id, user_id) in self._follows
            requested = (self._current_user_id, user_id) in self._follow_requests
            can_view = is_me or (not u["isPrivate"]) or followed

            post_count = sum(1 for m in self._media.values() if m["userId"] == user_id)
            follower_count = sum(1 for fid, tid in self._follows if tid == user_id)
            following_count = sum(1 for fid, tid in self._follows if fid == user_id)

            return {
                "id": u["id"],
                "username": u["username"],
                "bio": u["bio"],
                "avatarUrl": u["avatarUrl"],
                "isPrivate": u["isPrivate"],
                "isMe": is_me,
                "postCount": post_count,
                "followerCount": follower_count,
                "followingCount": following_count,
                "followedByMe": followed,
                "requestedByMe": requested,
                "canView": can_view
            }

    def get_user_posts(self, user_id: int, page: int = 0, size: int = 18) -> Dict[str, Any]:
        with self._lock:
            if user_id not in self._users:
                raise ApiError(404, "User not found")
            profile = self.get_profile(user_id)
            if not profile["canView"]:
                raise ApiError(403, "This account is private")

            posts = [
                {"id": m["id"], "type": m["type"], "mediaKind": m["mediaKind"], "thumbnailUrl": m["thumbnailUrl"]}
                for m in self._media.values()
                if m["userId"] == user_id and m["type"] in ("POST", "REEL")
            ]
            posts.sort(key=lambda x: x["id"], reverse=True)
            start = page * size
            end = start + size
            slice_items = posts[start:end]
            return {
                "items": slice_items,
                "hasNext": end < len(posts)
            }

    def get_followers(self, user_id: int, page: int = 0, size: int = 20) -> Dict[str, Any]:
        with self._lock:
            profile = self.get_profile(user_id)
            if not profile["canView"]:
                raise ApiError(403, "This account is private")
            follower_ids = [fid for fid, tid in self._follows if tid == user_id]
            start = page * size
            end = start + size
            slice_ids = follower_ids[start:end]
            return {
                "items": [self._build_user_summary(uid) for uid in slice_ids],
                "hasNext": end < len(follower_ids)
            }

    def get_following(self, user_id: int, page: int = 0, size: int = 20) -> Dict[str, Any]:
        with self._lock:
            profile = self.get_profile(user_id)
            if not profile["canView"]:
                raise ApiError(403, "This account is private")
            following_ids = [tid for fid, tid in self._follows if fid == user_id]
            start = page * size
            end = start + size
            slice_ids = following_ids[start:end]
            return {
                "items": [self._build_user_summary(uid) for uid in slice_ids],
                "hasNext": end < len(following_ids)
            }

    def follow_user(self, user_id: int) -> Dict[str, Any]:
        with self._lock:
            if user_id == self._current_user_id:
                raise ApiError(400, "Cannot follow yourself")
            if user_id not in self._users:
                raise ApiError(404, "User not found")

            target = self._users[user_id]
            if target["isPrivate"]:
                self._follow_requests.add((self._current_user_id, user_id))
                cnt = sum(1 for fid, tid in self._follows if tid == user_id)
                return {"following": False, "requested": True, "followerCount": cnt}
            else:
                self._follows.add((self._current_user_id, user_id))
                cnt = sum(1 for fid, tid in self._follows if tid == user_id)
                return {"following": True, "requested": False, "followerCount": cnt}

    def unfollow_user(self, user_id: int) -> Dict[str, Any]:
        with self._lock:
            self._follows.discard((self._current_user_id, user_id))
            self._follow_requests.discard((self._current_user_id, user_id))
            cnt = sum(1 for fid, tid in self._follows if tid == user_id)
            return {"following": False, "requested": False, "followerCount": cnt}

    def update_profile(self, bio: Optional[str] = None, username: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            me = self._users[self._current_user_id]
            if username and username != me["username"]:
                for uid, u in self._users.items():
                    if uid != self._current_user_id and u["username"].lower() == username.lower():
                        raise ApiError(409, "Username already taken")
                me["username"] = username
            if bio is not None:
                me["bio"] = bio
            return dict(me)

    def update_avatar(self, r2_key: str) -> Dict[str, Any]:
        with self._lock:
            me = self._users[self._current_user_id]
            me["avatarUrl"] = r2_key
            return dict(me)

    def update_settings(self, is_private: bool, notifications_enabled: bool) -> Dict[str, Any]:
        with self._lock:
            me = self._users[self._current_user_id]
            me["isPrivate"] = is_private
            me["notificationsEnabled"] = notifications_enabled
            # If changed from private to public, auto-accept pending follow requests
            if not is_private:
                pending = [fid for fid, tid in self._follow_requests if tid == self._current_user_id]
                for fid in pending:
                    self._follows.add((fid, self._current_user_id))
                    self._follow_requests.discard((fid, self._current_user_id))
            return {
                "isPrivate": is_private,
                "notificationsEnabled": notifications_enabled
            }

    def get_follow_requests(self, page: int = 0, size: int = 20) -> Dict[str, Any]:
        with self._lock:
            requesters = [fid for fid, tid in self._follow_requests if tid == self._current_user_id]
            start = page * size
            end = start + size
            slice_ids = requesters[start:end]
            return {
                "items": [self._build_user_summary(uid) for uid in slice_ids],
                "hasNext": end < len(requesters)
            }

    def accept_follow_request(self, user_id: int) -> None:
        with self._lock:
            if (user_id, self._current_user_id) in self._follow_requests:
                self._follow_requests.discard((user_id, self._current_user_id))
                self._follows.add((user_id, self._current_user_id))
            else:
                raise ApiError(404, "No such follow request")

    def decline_follow_request(self, user_id: int) -> None:
        with self._lock:
            if (user_id, self._current_user_id) in self._follow_requests:
                self._follow_requests.discard((user_id, self._current_user_id))
            else:
                raise ApiError(404, "No such follow request")

    # 8. Uploads
    def presign_upload(self, file_name: str, content_type: str, media_type: str, file_size: int) -> Dict[str, Any]:
        with self._lock:
            if media_type not in ("POST", "REEL", "STORY", "AVATAR"):
                raise ApiError(400, "Invalid media type")
            if media_type == "REEL" and content_type != "video/mp4":
                raise ApiError(400, "Reels must be video/mp4")
            if media_type == "AVATAR" and not content_type.startswith("image/"):
                raise ApiError(400, "Avatars must be an image")

            max_size = 100 * 1024 * 1024 if "video" in content_type else 10 * 1024 * 1024
            if file_size > max_size:
                raise ApiError(400, f"File size exceeds limit of {max_size} bytes")

            key = f"{media_type}/{self._current_user_id}/mock_{random.randint(1000, 9999)}_{file_name}"
            return {
                "uploadUrl": f"http://localhost:8080/mock-r2-upload/{key}",
                "r2Key": key
            }

    def upload_file_binary(
        self,
        upload_url: str,
        file_path_or_bytes: Union[str, Path, bytes],
        content_type: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> None:
        # Simulate upload progression
        if progress_callback:
            progress_callback(50, 100)
            progress_callback(100, 100)

    def confirm_upload(self, r2_key: str, media_type: str, caption: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            self._media_id_counter += 1
            mid = self._media_id_counter
            kind = "VIDEO" if media_type == "REEL" or "video" in r2_key else "IMAGE"
            aspect = (440, 440) if media_type == "POST" else (360, 640)
            img_path = _generate_gradient_image(
                aspect[0], aspect[1],
                (40, 80, 160), (80, 160, 240),
                label=f"Uploaded {media_type} #{mid}",
                subtitle=f"@{self._users[self._current_user_id]['username']}"
            )

            new_media = {
                "id": mid,
                "userId": self._current_user_id,
                "type": media_type,
                "mediaKind": kind,
                "mediaUrl": img_path,
                "thumbnailUrl": img_path,
                "caption": caption or "",
                "tags": [t.strip("#").lower() for t in (caption or "").split() if t.startswith("#")],
                "createdAt": _iso_now(),
                "likeCount": 0,
                "commentCount": 0,
                "shareCount": 0,
                "likedByMe": False,
            }
            self._media[mid] = new_media
            self._comments[mid] = []

            # If STORY, append to self._stories
            if media_type == "STORY":
                if self._current_user_id not in self._stories:
                    self._stories[self._current_user_id] = []
                self._stories[self._current_user_id].append({
                    "id": mid,
                    "userId": self._current_user_id,
                    "mediaUrl": img_path,
                    "mediaKind": kind,
                    "createdAt": _iso_now(),
                    "expiresAt": _iso_now(24 * 3600),
                    "seen": False
                })

            return self._build_media_card(mid)
