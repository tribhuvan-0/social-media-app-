# SocialApp Backend REST API

High-performance, production-ready Spring Boot 3.3+ REST API backend for the **SocialApp** Instagram-style desktop social media platform.

---

## Table of Contents

1. [Architecture & Technology Overview](#architecture--technology-overview)
2. [Prerequisites & System Dependencies](#prerequisites--system-dependencies)
3. [Database Setup & Provisioning](#database-setup--provisioning)
4. [Dual-Mode Media Storage](#dual-mode-media-storage)
5. [Video Processing & FFmpeg Thumbnails](#video-processing--ffmpeg-thumbnails)
6. [Reels Recommendation Engine](#reels-recommendation-engine)
7. [Environment Variables Reference](#environment-variables-reference)
8. [Build & Automated Verification Suite](#build--automated-verification-suite)
9. [Running the Application](#running-the-application)
10. [CLI Integration Test Runner (`test_api.py`)](#cli-integration-test-runner-test_apipy)
11. [Postman Collection (`SocialApp.postman_collection.json`)](#postman-collection-socialapppostman_collectionjson)
12. [cURL Command Examples](#curl-command-examples)
13. [Complete API Reference Catalog (34 Endpoints)](#complete-api-reference-catalog-34-endpoints)

---

## Architecture & Technology Overview

- **Runtime & Language**: Java 17+ baseline (tested and compatible with OpenJDK 17, 21, and 25).
- **Framework**: Spring Boot `3.3.4` (Spring Web, Spring Data JPA, Spring Security, Spring Validation).
- **Build System**: Apache Maven 3.9.6 with embedded executable Maven Wrapper (`./mvnw`).
- **Database Architecture**:
  - **Production & Development**: MariaDB / MySQL 8 on port 3306 with strict foreign key constraints (`ON DELETE CASCADE`), character set `utf8mb4`, and collation `utf8mb4_unicode_ci`.
  - **Automated Verification**: H2 in-memory database (`MODE=MySQL`) for fast, hermetic, zero-dependency test runs.
- **Security & Identity**:
  - Stateless HS256 JSON Web Token (JWT) authentication filter (`JwtAuthFilter`).
  - BCrypt password hashing (cost factor 10).
  - RFC 7807 compliant standardized JSON error responses with ISO-8601 UTC timestamps.
- **Dual-Mode Media Storage**:
  - **Cloudflare R2**: S3-compatible cloud storage via AWS SDK for Java v2 (`2.25.60`) using presigned PUT URLs with 10-minute expiry.
  - **Local Storage Fallback**: Automatic offline filesystem storage (`/api/uploads/local-storage/...`) allowing 100% offline development and air-gapped testing.
- **Video Thumbnail Extraction**: Dedicated asynchronous thread pool (`thumbnailTaskExecutor`) executing FFmpeg via `ProcessBuilder` with 480px width scaling and standard I/O pipe draining.
- **Recommendation Engine**: Multi-pool scoring (Personalized 40%, Exploration 30%, Popular 30%) with watch duration telemetry, daily decay, and creator anti-clumping.
- **N+1 Query Elimination**: Batch-loaded repository mappers fetching relational entities in constant queries with `IN` clauses.
- **Atomic Counters**: Direct SQL `UPDATE ... SET count = count + 1` expressions eliminating race conditions on likes, comments, shares, and views.
- **Seed Data Runner**: `CommandLineRunner` populating 6 demo accounts and 24 rich posts, reels, and stories with authentic tags and relationships.

---

## Prerequisites & System Dependencies

### 1. Java Development Kit (JDK 17+)
Verify installed Java version:
```bash
java -version
```
If not installed:
- **Ubuntu/Debian**: `sudo apt update && sudo apt install -y openjdk-17-jdk`
- **Arch Linux**: `sudo pacman -S jdk17-openjdk`
- **macOS**: `brew install openjdk@17`
- **Windows**: Download and install Eclipse Temurin 17 or Oracle JDK 17.

### 2. MariaDB or MySQL 8
Verify database status:
```bash
systemctl status mariadb || systemctl status mysql
```
If not installed:
- **Ubuntu/Debian**: `sudo apt install -y mariadb-server && sudo systemctl enable --now mariadb`
- **Arch Linux**: `sudo pacman -S mariadb && sudo mariadb-install-db --user=mysql --basedir=/usr --datadir=/var/lib/mysql && sudo systemctl enable --now mariadb`
- **macOS**: `brew install mariadb && brew services start mariadb`

### 3. FFmpeg (for Video Thumbnails)
Verify FFmpeg installation:
```bash
ffmpeg -version
```
If not installed:
- **Ubuntu/Debian**: `sudo apt install -y ffmpeg`
- **Arch Linux**: `sudo pacman -S ffmpeg`
- **macOS**: `brew install ffmpeg`
- **Windows**: Download FFmpeg static build from `ffmpeg.org` and add its `bin/` directory to your system `PATH`.

### 4. Python 3.8+ (for CLI Test Runner)
```bash
python3 --version
```

---

## Database Setup & Provisioning

### Step 1: Create Database & User
Run `setup-db.sql` using the MySQL/MariaDB root user:
```bash
mysql -u root -p < setup-db.sql
# Or on MariaDB systems with socket authentication:
sudo mariadb < setup-db.sql
```

This creates:
- Database: `socialapp` (character set `utf8mb4`, collation `utf8mb4_unicode_ci`)
- User: `socialapp` with password `socialapp`
- Granted privileges: `ALL PRIVILEGES ON socialapp.*` to `'socialapp'@'localhost'` and `'socialapp'@'%'`

### Step 2: Initialize Tables & Indexes
Run `schema.sql` to apply the production schema:
```bash
mysql -u socialapp -psocialapp socialapp < schema.sql
```

This provisions all 11 core tables:
1. `users` (accounts, BCrypt credentials, privacy toggles)
2. `media` (POST, REEL, STORY items with atomic counters)
3. `media_tags` (extracted hashtags)
4. `likes` (idempotent user media likes)
5. `comments` (threaded chronological comments)
6. `follows` (unidirectional follower relationships)
7. `follow_requests` (inbound private profile requests)
8. `story_views` (idempotent 24h story tracking)
9. `media_views` (watch time duration telemetry)
10. `shares` (share tracking and URL dispatch)
11. `user_interests` (algorithmic hashtag interest scores clamped to [-20, 100])

*Note: Automated tests execute against the embedded H2 in-memory database (`src/test/resources/schema-h2.sql`) and do not modify your MariaDB database.*

---

## Dual-Mode Media Storage

SocialApp features a transparent Dual-Mode Media Storage subsystem:

```
                      +-----------------------------+
                      |       StorageService        |
                      +-----------------------------+
                                     |
                 +-------------------+-------------------+
                 |                                       |
    [STORAGE_MODE=r2]                       [STORAGE_MODE=local]
                 v                                       v
    +-------------------------+             +-------------------------+
    |    R2StorageService     |             |   LocalStorageService   |
    |  (AWS SDK v2 S3Client)  |             |  (Direct Disk Fallback) |
    +-------------------------+             +-------------------------+
                 |                                       |
                 v                                       v
      Cloudflare R2 Bucket                  Local Directory (media-storage/)
   Presigned PUT URLs (10 min)             Endpoint: /api/uploads/local-storage/**
```

### 1. Cloudflare R2 Mode
To use Cloudflare R2:
1. Create an R2 bucket named `socialapp` in your Cloudflare dashboard.
2. In bucket settings, connect a custom domain or enable the `pub-r2.dev` public access subdomain.
3. Generate an R2 API Token with **Object Read & Write** permissions.
4. Set the following environment variables in `.env`:
   ```bash
   STORAGE_MODE=r2
   R2_ACCOUNT_ID=your_cloudflare_account_id
   R2_ACCESS_KEY=your_r2_access_key_id
   R2_SECRET_KEY=your_r2_secret_access_key
   R2_BUCKET=socialapp
   R2_PUBLIC_BASE_URL=https://pub-r2.dev/your-bucket-path
   ```

### 2. Local Storage Fallback Mode (Offline Default)
When `STORAGE_MODE=local` (or R2 variables are blank):
- The server stores uploaded assets directly on the local filesystem under `LOCAL_STORAGE_DIR` (default: `./media-storage`).
- `POST /api/uploads/presign` returns direct upload URLs pointing to `http://localhost:8080/api/uploads/local-storage/{r2Key}`.
- `PUT /api/uploads/local-storage/{r2Key}` streams binary image/video bytes directly to disk.
- `GET /api/uploads/local-storage/{r2Key}` streams the stored binary assets back with correct MIME types and `Accept-Ranges` byte-range headers.
- **100% offline development**: No internet connection, AWS account, or cloud service required.

---

## Video Processing & FFmpeg Thumbnails

Video uploads (`REEL`, video `POST`, video `STORY`) automatically trigger background thumbnail extraction:
1. When `POST /api/uploads/confirm` completes, `FfmpegThumbnailService` receives an asynchronous event on the `thumbnailTaskExecutor` thread pool.
2. The service creates an isolated temporary directory and extracts a single high-quality frame at `1.0s` scaled to 480px width (`-vf scale=480:-2`):
   ```bash
   ffmpeg -y -ss 1.0 -i input.mp4 -vframes 1 -vf scale=480:-2 thumb.jpg
   ```
3. If the video is shorter than 1.0s or the 1.0s frame fails, it automatically retries at `-ss 0.0`.
4. The extracted JPEG is uploaded to storage at `thumbnails/{userId}/{uuid}.jpg` and `Media.thumbnailKey` is updated atomically.
5. All standard output and error streams are drained asynchronously to prevent OS pipe deadlocks.
6. A 30-second execution timeout is enforced with forcible process termination (`process.destroyForcibly()`).
7. Temporary directories are safely removed in a `finally` block.

---

## Reels Recommendation Engine

SocialApp implements an Instagram-grade 3-Pool Recommendation Engine:

```
                    +---------------------------+
                    |    Candidate Selection    |
                    |  (REEL, not mine, not in  |
                    |   exclude, not seen in 7d)|
                    +---------------------------+
                                  |
         +------------------------+------------------------+
         |                                                 |
         v                                                 v
  [Cold User (<10 views)]                       [Normal Active User]
  - 80% Exploration                             - 40% Personalized
  - 20% Popular                                 - 30% Exploration
  -  0% Personalized                            - 30% Popular
         |                                                 |
         +------------------------+------------------------+
                                  |
                                  v
                    +---------------------------+
                    |  Creator Anti-Clumping    |
                    | (No consecutive creators) |
                    +---------------------------+
                                  |
                                  v
                    +---------------------------+
                    |  Dynamic Pool Fill &      |
                    |  Small-Catalog Loopback   |
                    +---------------------------+
```

### 1. Multi-Pool Scoring
- **Personalized Pool (40%)**:
  Identifies reels containing hashtags where user has positive interest scores:
  $$\text{Score} = \left(\sum \text{Interest}(tag)\right) \times \left(\frac{1}{1 + \text{AgeDays}/7}\right) \times (1 + \log_{10}(1 + \text{Engagement}))$$
- **Exploration Pool (30%)**:
  Discovers fresh content with tags outside user's top 10 interests.
- **Popular Pool (30%)**:
  Calculates platform-wide trending velocity:
  $$\text{Score} = \frac{\text{Likes} \times 3 + \text{Comments} \times 4 + \text{Shares} \times 5 + \text{Views}}{(\text{AgeHours} + 2)^{1.2}}$$

### 2. Interaction Telemetry Weights
Interactions dynamically update user interest scores (clamped between `[-20.0, 100.0]`):
- Full video watch ($\ge 80\%$ duration or completed): `+2.0`
- Repeated loop playback: `+1.0`
- Partial watch ($> 2.0\text{s}$ and $< 80\%$): `+0.5`
- Skip ($< 2.0\text{s}$): `-2.0`
- Like / Unlike: `+4.0` / `-4.0`
- Comment: `+5.0`
- Share: `+6.0`
- Follow creator: `+5.0` on creator's top 3 tags

### 3. Scheduled Maintenance
- **Story Expiry**: Runs every 10 minutes, purging expired stories (`expires_at < NOW()`) and storage assets.
- **Daily Decay**: Runs daily at 03:00, decaying all user interest scores by $0.95$ and purging entries with $|\text{score}| < 0.5$.
- **Views Pruning**: Runs weekly, deleting `media_views` older than 90 days.

---

## Environment Variables Reference

Copy `.env.example` to `.env` or set the following variables:

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `SERVER_PORT` | `8080` | HTTP port for the Spring Boot application |
| `SPRING_PROFILES_ACTIVE` | `dev` | Active Spring profile (`dev`, `prod`, `test`) |
| `DB_URL` | `jdbc:mysql://localhost:3306/socialapp?...` | MariaDB / MySQL JDBC connection URL |
| `DB_USER` | `socialapp` | Database username |
| `DB_PASS` | `socialapp` | Database password |
| `JWT_SECRET` | `c29jaWFsYXBwLXNlY3JldC1rZXkt...` | Base64-encoded secret for HS256 JWT tokens ($\ge 256$ bits) |
| `JWT_EXPIRY_HOURS` | `168` | JWT expiration time in hours (default: 7 days) |
| `APP_BASE_URL` | `http://localhost:8080` | Public base URL used to generate share links (`/m/{id}`) |
| `STORAGE_MODE` | `local` | Storage mode: `local` (disk fallback) or `r2` (Cloudflare R2) |
| `LOCAL_STORAGE_DIR` | `./media-storage` | Local directory for uploaded files when `STORAGE_MODE=local` |
| `R2_ACCOUNT_ID` | *(empty)* | Cloudflare R2 Account ID |
| `R2_ACCESS_KEY` | *(empty)* | Cloudflare R2 Access Key ID |
| `R2_SECRET_KEY` | *(empty)* | Cloudflare R2 Secret Access Key |
| `R2_BUCKET` | `socialapp` | Cloudflare R2 bucket name |
| `R2_PUBLIC_BASE_URL` | `https://pub-r2.dev` | Public CDN URL for Cloudflare R2 assets |
| `FFMPEG_PATH` | `/usr/sbin/ffmpeg` | Path to FFmpeg binary for thumbnail generation |
| `PLACEHOLDER_THUMB_URL` | `http://localhost:8080/placeholder-thumb.jpg` | Fallback thumbnail URL when extraction fails |

---

## Build & Automated Verification Suite

Run the full automated test suite using the standalone Maven wrapper:

```bash
# Run 100% of unit, repository, and MockMvc integration tests
./mvnw clean test

# Run complete verification lifecycle and build executable JAR
./mvnw clean verify
```

### Test Coverage Highlights (98 Automated Tests, 0 Failures)
- **Authentication**: `AuthControllerTest`, `JwtTokenProviderTest` (signup, duplicate 409, bad credentials 401, token validation, password update).
- **Feed & Discovery**: `FeedControllerTest` (pagination, followed user filtering, suggested accounts).
- **Stories**: `StoriesControllerTest` (grouping, seen tracking idempotency, expiration rules).
- **Reels Engine**: `ReelsControllerTest`, `RecommendationServiceTest` (cold start exploration mix, interest weighting, candidate exclusion, loopback).
- **Media & Interactions**: `MediaControllerTest` (atomic likes, shares, comments, private account 403, owner-only deletion).
- **Social Graph**: `UserControllerTest`, `FollowRequestControllerTest` (follow, unfollow, private requests, accept/decline).
- **Storage & Uploads**: `UploadControllerTest`, `LocalStorageServiceTest`, `FfmpegThumbnailServiceTest`, `StoragePropertiesTest` (presigning, binary PUT/GET, FFmpeg 480px scaling, traversal guards).
- **Database Schema Integrity**: `HibernateSchemaValidationTest`, `JpaSchemaIntegrityTest`, `MySqlSchemaParseTest`.

---

## Running the Application

### Option A: Development Mode (with Demo Seed Data)
Starts Spring Boot with MariaDB and populates 6 demo users (`Password123!`), 18 follow relationships, and 24 sample posts/reels:
```bash
./mvnw spring-boot:run -Dspring-boot.run.profiles=dev
```

### Option B: Zero-Dependency In-Memory Demo Mode
Runs the backend completely in-memory using H2 (no database setup required):
```bash
./mvnw spring-boot:run -Dspring-boot.run.profiles=test
```

### Option C: Production Executable JAR
```bash
# 1. Package the application
./mvnw clean package -DskipTests

# 2. Run the packaged JAR
java -jar target/socialapp-backend-1.0.0-SNAPSHOT.jar
```

### Default Demo Accounts (Available in `dev` Profile)
All demo accounts are pre-seeded with password `Password123!`:
- `elena_v` (Visual artist & photographer in Berlin)
- `marcus_tech` (Full-stack engineer & AI researcher)
- `sophia_chef` (Culinary explorer & pastry chef)
- `alex_travels` (Nomad & adventure filmmaker)
- `maya_fitness` (Holistic wellness coach)
- `david_music` (Indie composer & producer)

---

## CLI Integration Test Runner (`test_api.py`)

The repository includes a comprehensive, standalone Python 3 CLI test runner that executes 44 end-to-end integration tests against a running backend server.

### Features
- **Zero External Dependencies**: Built with Python standard library (`urllib.request`, `json`, `argparse`).
- **Complete Endpoint Coverage**: Exercises auth, uploads, binary storage PUT/GET, feed, stories, reels recommendations, likes, comments, shares, telemetry, and private follow requests.
- **Clean Colored Output**: Visual test progress with execution latencies, summary box, and exit code 0 on success.

### Usage
```bash
# Ensure the backend server is running on port 8080 first
python3 test_api.py

# Specify a custom base URL
python3 test_api.py --base-url http://localhost:8080/api

# Enable verbose mode (displays all HTTP request & response JSON payloads)
python3 test_api.py --verbose

# Disable ANSI colors for log files
python3 test_api.py --no-color
```

### Sample Output
```
╔══════════════════════════════════════════════════════════════════════════╗
║                 SocialApp API Comprehensive Verification                 ║
╚══════════════════════════════════════════════════════════════════════════╝
Target API: http://localhost:8080/api

=== 1. Authentication & Account Management ===
  • POST /api/auth/signup (User 1)                          [PASS] ( 42.1ms)
  • POST /api/auth/signup (409 Conflict validation)          [PASS] (  8.4ms)
  • POST /api/auth/login (User 1)                           [PASS] ( 12.3ms)
  • POST /api/auth/login (401 Bad Credentials)              [PASS] (  7.8ms)
  • GET /api/auth/me (Current User Profile)                 [PASS] (  5.2ms)
  • PUT /api/auth/password (Change Password)                [PASS] ( 14.1ms)
  • POST /api/auth/login (Verify New Password)              [PASS] ( 11.9ms)
  • POST /api/auth/signup (User 2 for Social Graph)         [PASS] ( 18.4ms)

=== 2. Dual-Mode Storage & Upload Pipelines ===
  • POST /api/uploads/presign (Image Upload)                [PASS] (  6.1ms)
  • PUT /api/uploads/local-storage/** (Binary Upload)       [PASS] (  9.5ms)
  • GET /api/uploads/local-storage/** (Binary Serve)        [PASS] (  4.8ms)
  • POST /api/uploads/confirm (Create Media & Extract Tags) [PASS] ( 22.4ms)
  • POST /api/uploads/confirm (403 Key Ownership Guard)     [PASS] (  4.2ms)
  • POST /api/uploads/presign (400 REEL Content-Type Validation) [PASS] (  3.9ms)
...
══════════════════════════════════════════════════════════════════════════
SocialApp REST API Integration Verification Summary
══════════════════════════════════════════════════════════════════════════
  Total Functional Tests: 44
  Passed:                 44
  Failed:                 0

✓ ALL API FUNCTIONAL VERIFICATION TESTS PASSED SUCCESSFULLY!
```

---

## Postman Collection (`SocialApp.postman_collection.json`)

The file `SocialApp.postman_collection.json` adheres to the official **Postman Collection Schema v2.1.0** and covers all 34 API endpoints organized into 7 domain folders.

### Importing into Postman
1. Open the Postman Desktop App or Postman Web.
2. Click **Import** in the top-left corner.
3. Drag and drop `backend/SocialApp.postman_collection.json`.
4. The collection is pre-configured with collection variables:
   - `baseUrl`: `http://localhost:8080/api`
   - `token`: automatically populated by pre-request/test scripts on Signup & Login.
   - `myUserId`, `targetUserId`, `mediaId`, `commentId`, `storyId`, `r2Key`.

### Running with Newman (CLI)
You can run the entire Postman collection in headless CI/CD using Newman:
```bash
# Install Newman if not already present
npm install -g newman

# Run the collection against the running server
newman run SocialApp.postman_collection.json
```

---

## cURL Command Examples

### 1. User Signup
```bash
curl -i -X POST http://localhost:8080/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "username": "developer_jane",
    "email": "jane@example.com",
    "password": "Password123!"
  }'
```

### 2. User Login
```bash
curl -i -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "developer_jane",
    "password": "Password123!"
  }'
```
*Save the returned `"token"` for subsequent requests.*

### 3. Get Current User (`me`)
```bash
curl -i -X GET http://localhost:8080/api/auth/me \
  -H "Authorization: Bearer <TOKEN>"
```

### 4. Presign Upload (Image)
```bash
curl -i -X POST http://localhost:8080/api/uploads/presign \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "fileName": "landscape.jpg",
    "contentType": "image/jpeg",
    "type": "POST",
    "fileSize": 204800
  }'
```
*Returns `uploadUrl` and `r2Key` (e.g. `POST/1/uuid-landscape.jpg`).*

### 5. Binary Upload to Local Storage Fallback
```bash
curl -i -X PUT "http://localhost:8080/api/uploads/local-storage/POST/1/uuid-landscape.jpg" \
  -H "Content-Type: image/jpeg" \
  --data-binary @landscape.jpg
```

### 6. Confirm Upload
```bash
curl -i -X POST http://localhost:8080/api/uploads/confirm \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "r2Key": "POST/1/uuid-landscape.jpg",
    "type": "POST",
    "caption": "Sunrise over the Baltic Sea #baltic #sunrise #nature"
  }'
```

### 7. For You Feed
```bash
curl -i -X GET "http://localhost:8080/api/feed?page=0&size=10" \
  -H "Authorization: Bearer <TOKEN>"
```

### 8. Reels Recommendations Feed
```bash
curl -i -X GET "http://localhost:8080/api/reels?size=5&exclude=12,45" \
  -H "Authorization: Bearer <TOKEN>"
```

### 9. Like Media Post
```bash
curl -i -X POST http://localhost:8080/api/media/1/like \
  -H "Authorization: Bearer <TOKEN>"
```

### 10. Follow User
```bash
curl -i -X POST http://localhost:8080/api/users/2/follow \
  -H "Authorization: Bearer <TOKEN>"
```

---

## Complete API Reference Catalog (34 Endpoints)

| # | Domain | Method | Endpoint Path | Status | Description |
|---|--------|--------|---------------|--------|-------------|
| 1 | Auth | `POST` | `/api/auth/signup` | 201 | Register account with BCrypt password hashing |
| 2 | Auth | `POST` | `/api/auth/login` | 200 | Authenticate credentials and receive JWT |
| 3 | Auth | `GET` | `/api/auth/me` | 200 | Current authenticated user profile and flags |
| 4 | Auth | `PUT` | `/api/auth/password` | 204 | Change password with old password verification |
| 5 | Feed | `GET` | `/api/feed?page=0&size=10` | 200 | Paged posts & reels from followed users and self |
| 6 | Feed | `GET` | `/api/users/suggested` | 200 | Top 10 recommended unfollowed accounts |
| 7 | Stories | `GET` | `/api/stories` | 200 | Active 24h stories grouped by user |
| 8 | Stories | `POST` | `/api/stories/{id}/seen` | 204 | Idempotent story view tracking |
| 9 | Reels | `GET` | `/api/reels?size=5&exclude=...` | 200 | 3-pool Reels recommendation feed |
| 10 | Media | `GET` | `/api/media/{id}` | 200 | Media detail with privacy check |
| 11 | Media | `DELETE` | `/api/media/{id}` | 204 | Owner-only deletion with asset purge |
| 12 | Media | `POST` | `/api/media/{id}/like` | 200 | Idempotent like with counter increment |
| 13 | Media | `DELETE` | `/api/media/{id}/like` | 200 | Idempotent unlike with counter decrement |
| 14 | Media | `POST` | `/api/media/{id}/share` | 200 | Share counter increment and URL dispatch |
| 15 | Media | `POST` | `/api/media/{id}/view` | 204 | Watch duration and completion telemetry |
| 16 | Media | `GET` | `/api/media/{id}/comments?page=0&size=20` | 200 | Paged comments ordered oldest first |
| 17 | Media | `POST` | `/api/media/{id}/comments` | 201 | Add comment with atomic counter increment |
| 18 | Media | `DELETE` | `/api/comments/{id}` | 204 | Delete comment (author or post owner) |
| 19 | Users | `GET` | `/api/users/{id}/profile` | 200 | User profile with counts and `canView` flag |
| 20 | Users | `GET` | `/api/users/{id}/posts?page=0&size=18` | 200 | 3-column media grid for profile |
| 21 | Users | `GET` | `/api/users/{id}/followers?page=0&size=20` | 200 | Paged list of user's followers |
| 22 | Users | `GET` | `/api/users/{id}/following?page=0&size=20` | 200 | Paged list of accounts user follows |
| 23 | Users | `POST` | `/api/users/{id}/follow` | 200 | Follow public user or request private user |
| 24 | Users | `DELETE` | `/api/users/{id}/follow` | 200 | Unfollow user or cancel pending request |
| 25 | Users | `PUT` | `/api/users/me` | 200 | Partial update of user's bio and username |
| 26 | Users | `PUT` | `/api/users/me/avatar` | 200 | Update avatar key and delete old asset |
| 27 | Users | `PUT` | `/api/users/me/settings` | 200 | Toggle private profile and notifications |
| 28 | Users | `GET` | `/api/follow-requests?page=0&size=20` | 200 | Inbound pending follow requests |
| 29 | Users | `POST` | `/api/follow-requests/{userId}/accept` | 204 | Accept follow request establishing follow |
| 30 | Users | `POST` | `/api/follow-requests/{userId}/decline` | 204 | Decline and delete follow request |
| 31 | Upload | `POST` | `/api/uploads/presign` | 200 | Issue presigned PUT URL or local upload URL |
| 32 | Upload | `POST` | `/api/uploads/confirm` | 201 | Confirm asset, extract tags, trigger FFmpeg |
| 33 | Storage | `PUT` | `/api/uploads/local-storage/**` | 200 | Binary upload endpoint for offline dev |
| 34 | Storage | `GET` | `/api/uploads/local-storage/**` | 200 | Binary serve endpoint for offline dev |
