# SocialApp Desktop Client (Python / CustomTkinter + VLC)

Modern Instagram-style desktop social media client built with Python 3.11+, CustomTkinter, Pillow, and python-vlc.

---

## 1. Architectural Highlights

- **Window Dimensions**: Fixed `480x860` mobile aspect ratio, centered, non-resizable mobile UI feel.
- **Embedded Video Playback**: Single shared `SharedVlcPlayer` across the entire application embedded directly into native Tk frame canvas windows via platform window IDs (`set_xwindow` on Linux, `set_hwnd` on Windows, `set_nsobject` on macOS). Includes full headless fallback to `MockVlcPlayer` for environments without VLC native shared libraries.
- **Thread Safety & Async Queue**: 4-worker `ThreadPoolExecutor` paired with a thread-safe `queue.Queue`. Main thread drains queue every 40ms via `start_queue_pump(root, 40)`. All API and heavy image processing runs off the UI thread via `run_async(fn, on_success, on_error)`.
- **Dual-Tier Image Cache**: 300-entry in-memory LRU cache + persistent SHA-256 on-disk cache in `~/.cache/socialapp/images/` with anti-aliased Pillow circular and rounded alpha masks.
- **Stack-Based Navigation Router**: `NavigationRouter` managing 5 primary bottom navigation tabs (Home, Explore, Create, Reels, Profile), nested push/pop history, top-bar Back button, fullscreen Stories Viewer overlay, and `on_enter()` / `on_leave()` hooks.
- **Dual-Mode Backend Adapter**:
  - `ApiClient`: Authoritative HTTP client calling Spring Boot REST endpoints with memory-only JWT token, 401 interceptor, and streaming binary PUT uploads.
  - `MockApi`: 100% offline demo mode seeded with 6 realistic users, dynamic Pillow-generated media, and composite endpoints.

---

## 2. Prerequisites & Installation

### System Dependencies
- Python 3.11 or newer
- VLC Media Player (must match Python architecture, e.g. 64-bit VLC for 64-bit Python):
  - **Linux (Debian/Ubuntu)**: `sudo apt-get install vlc libvlc-dev python3-tk`
  - **Linux (Arch/Manjaro)**: `sudo pacman -S vlc tk`
  - **Linux (Fedora/RHEL)**: `sudo dnf install vlc vlc-devel python3-tkinter`
  - **Windows**: Install 64-bit VLC from [videolan.org](https://www.videolan.org/vlc/).
  - **macOS**: Install VLC via `brew install --cask vlc`.

### Python Dependencies
Install the required packages from `requirements.txt`:
```bash
pip install -r frontend/requirements.txt
```

---

## 3. Configuration

Configuration options can be set via environment variables or stored in `~/.socialapp/config.json`:

| Variable | Default Value | Description |
|---|---|---|
| `BASE_URL` | `http://localhost:8080/api` | Spring Boot backend REST API base URL |
| `USE_MOCK` | `0` (or `1` if backend unreachable) | Force offline demo mode using Pillow-generated media |
| `MOCK_VIDEO_URL` | `""` | Optional video URL for playback in mock mode |

---

## 4. Running the Client

### Demo Mode (100% Offline with Seed Data)
To run the client completely standalone without needing the Spring Boot backend or database running:
```bash
export USE_MOCK=1
python3 -m frontend.main
```
or directly:
```bash
python3 frontend/main.py
```
*(If the backend is not reachable at startup on `http://localhost:8080/api`, SocialApp automatically engages `MockApi` with demo accounts).*

### Live Mode (Connecting to Spring Boot Backend)
Ensure the Spring Boot backend is running on port 8080:
```bash
unset USE_MOCK
python3 frontend/main.py
```

---

## 5. UI Screen Architecture

All screen modules are located in `frontend/screens/` and implement the `on_enter()` and `on_leave()` lifecycle hooks:

1. **`login.py` (LoginScreen)**: Login and Signup tabs, username/email/password inputs, client-side regex validation, inline error alerts, session saving in AppState, and transition to Home.
2. **`home.py` (HomeScreen)**: Top bar with logo and Direct Messages launcher, horizontal Stories tray with `StoryRing` items, scrollable feed of `PostCard` items with optimistic like toggle, comment modal opener, share link copier, suggested users empty state, and infinite scroll.
3. **`stories.py` (StoriesViewerModal & StoriesScreen)**: In-window Stories Viewer overlay (`360x640`), user header, segmented progress bars (5s countdown per image), auto-advancing across story groups, tap left/right to navigate, hold-to-pause, and seen status reporting.
4. **`reels.py` (ReelsScreen)**: Full-height 9:16 vertical video player embedded with `SharedVlcPlayer`, video loop, wheel/arrow navigation, action sidebar (heart, comment, share), and recommendation telemetry (`POST /api/media/{id}/view`).
5. **`explore.py` (ExploreScreen)**: Search bar filtering tags and accounts, suggested creators row, and 3-column media discovery grid with video badges.
6. **`create.py` (CreateScreen)**: Mode toggle (Post / Reel / Story), file picker with format and size validation (10MB image, 100MB video), real-time hashtag chip detection, streaming binary upload with progress bar, and confirm flow.
7. **`profile.py` (ProfileScreen)**: User profile header with 86px avatar, post/follower/following counts, follow/unfollow toggle, private account lock screen, tab selector (Posts/Reels), 3-column media grid, and edit profile dialog.
8. **`messages.py` (MessagesScreen)**: Direct Messages inbox, conversation threads, sent and received chat bubbles, and text message input.
9. **`activity.py` (ActivityScreen)**: Inbound follow requests with Accept and Decline actions, and interaction notifications feed.
10. **`settings.py` (SettingsScreen)**: Appearance theme switcher (Dark / Light / System), password update, private account and push notifications switches, disk cache size calculator and "Clear Cache" button, and confirmation logout.
11. **Auxiliary Modals**:
    - `comments.py` (`CommentsModal`): 420x600 dialog with scrollable comments list, add comment input, and author/owner delete actions.
    - `follow_list.py` (`FollowListModal`): Followers and following modal with paginated `UserRow` list.

---

## 6. Automated Verification

The frontend client includes three automated verification suites:

1. **Bytecode Compilation**:
   ```bash
   python3 -m py_compile frontend/*.py frontend/screens/*.py
   ```
2. **MockApi Contract Tests**:
   ```bash
   python3 frontend/test_mock_api.py
   ```
3. **Core Architecture Tests**:
   ```bash
   python3 frontend/test_core_architecture.py
   ```
4. **UI Screens & Integration Tests**:
   ```bash
   python3 frontend/test_ui_screens.py
   ```

---

## 7. Troubleshooting

### 1. VLC Not Found or Native Binding Issues
- **Symptom**: `ModuleNotFoundError: No module named 'vlc'` or `NameError: LibVLC not found`.
- **Resolution**: `player.py` automatically detects when `vlc` bindings are missing and activates `MockVlcPlayer` with zero crashes. To enable native playback, ensure 64-bit VLC desktop app is installed on your operating system and install `python-vlc`:
  ```bash
  pip install python-vlc
  ```

### 2. Video Window Embedding on Linux / Wayland
- **Symptom**: Video plays in a separate window or renders a black frame under Wayland.
- **Resolution**: Run the client with XWayland compatibility by forcing the X11 backend:
  ```bash
  GDK_BACKEND=x11 python3 frontend/main.py
  ```

### 3. Session Expiry (401 Loops)
- **Symptom**: Infinite redirection to login screen.
- **Resolution**: When a 401 response is intercepted, `ApiClient` immediately clears the in-memory JWT token, stops active playback in `SharedVlcPlayer`, and switches the navigation router to `LoginScreen` with a "Session expired" toast.
