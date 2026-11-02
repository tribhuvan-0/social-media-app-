package com.socialapp.seed;

import com.socialapp.entity.*;
import com.socialapp.entity.enums.MediaKind;
import com.socialapp.entity.enums.MediaType;
import com.socialapp.repository.UserRepository;
import com.socialapp.service.StorageService;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.io.InputStream;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Slf4j
@Component
@RequiredArgsConstructor
public class DataSeeder implements CommandLineRunner {

    private static final Pattern HASHTAG_PATTERN = Pattern.compile("#([A-Za-z0-9_]{1,30})");

    // Minimal 1x1 valid JPEG byte array
    private static final byte[] SAMPLE_JPEG = new byte[] {
            (byte) 0xFF, (byte) 0xD8, (byte) 0xFF, (byte) 0xE0, 0x00, 0x10, 0x4A, 0x46,
            0x49, 0x46, 0x00, 0x01, 0x01, 0x01, 0x00, 0x60, 0x00, 0x60, 0x00, 0x00,
            (byte) 0xFF, (byte) 0xDB, 0x00, 0x43, 0x00, 0x08, 0x06, 0x06, 0x07, 0x06,
            0x05, 0x08, 0x07, 0x07, 0x07, 0x09, 0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D,
            0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12, 0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F,
            0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20, 0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C,
            0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29, 0x2C, 0x30, 0x31, 0x34, 0x34, 0x34,
            0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32, 0x3C, 0x2E, 0x33, 0x34, 0x32, (byte) 0xFF,
            (byte) 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01, 0x00, 0x01, 0x01, 0x01, 0x11,
            0x00, (byte) 0xFF, (byte) 0xC4, 0x00, 0x1F, 0x00, 0x00, 0x01, 0x05, 0x01,
            0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B,
            (byte) 0xFF, (byte) 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00,
            (byte) 0xBF, (byte) 0x80, (byte) 0xFF, (byte) 0xD9
    };

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final StorageService storageService;

    @PersistenceContext
    private EntityManager entityManager;

    private byte[] loadSampleMp4() {
        try (InputStream in = getClass().getResourceAsStream("/sample_tiny.mp4")) {
            if (in != null) {
                return in.readAllBytes();
            }
        } catch (IOException e) {
            log.warn("Failed to load /sample_tiny.mp4 from classpath: {}", e.getMessage());
        }
        return SAMPLE_JPEG;
    }

    @Override
    @Transactional
    public void run(String... args) {
        if (userRepository.count() > 0) {
            log.info("Database already contains users. Skipping demo data seeding.");
            return;
        }

        log.info("Starting database seeding: 6 demo users, follows, and 24 media items...");

        byte[] sampleMp4 = loadSampleMp4();
        String encodedPassword = passwordEncoder.encode("Password123!");
        Instant baseTime = Instant.now().minus(30, ChronoUnit.DAYS);

        // 1. Create 6 Demo Users
        List<User> users = List.of(
                User.builder()
                        .username("elena_v")
                        .email("elena@example.com")
                        .passwordHash(encodedPassword)
                        .bio("Visual artist & photographer in Berlin. Capturing light and shadows.")
                        .isPrivate(false)
                        .notificationsEnabled(true)
                        .createdAt(baseTime)
                        .build(),
                User.builder()
                        .username("marcus_tech")
                        .email("marcus@example.com")
                        .passwordHash(encodedPassword)
                        .bio("Full-stack engineer & AI researcher. Building the future one commit at a time.")
                        .isPrivate(false)
                        .notificationsEnabled(true)
                        .createdAt(baseTime.plus(1, ChronoUnit.DAYS))
                        .build(),
                User.builder()
                        .username("sophia_chef")
                        .email("sophia@example.com")
                        .passwordHash(encodedPassword)
                        .bio("Culinary explorer & pastry chef. Creating sweet moments every day.")
                        .isPrivate(false)
                        .notificationsEnabled(true)
                        .createdAt(baseTime.plus(2, ChronoUnit.DAYS))
                        .build(),
                User.builder()
                        .username("alex_travels")
                        .email("alex@example.com")
                        .passwordHash(encodedPassword)
                        .bio("Nomad & adventure filmmaker. 45 countries and counting.")
                        .isPrivate(false)
                        .notificationsEnabled(true)
                        .createdAt(baseTime.plus(3, ChronoUnit.DAYS))
                        .build(),
                User.builder()
                        .username("maya_fitness")
                        .email("maya@example.com")
                        .passwordHash(encodedPassword)
                        .bio("Holistic wellness coach & marathon runner. Mindful movement.")
                        .isPrivate(false)
                        .notificationsEnabled(true)
                        .createdAt(baseTime.plus(4, ChronoUnit.DAYS))
                        .build(),
                User.builder()
                        .username("david_music")
                        .email("david@example.com")
                        .passwordHash(encodedPassword)
                        .bio("Producer & multi-instrumentalist. Soundscapes for daydreamers.")
                        .isPrivate(false)
                        .notificationsEnabled(true)
                        .createdAt(baseTime.plus(5, ChronoUnit.DAYS))
                        .build()
        );

        for (User u : users) {
            entityManager.persist(u);
        }
        entityManager.flush();

        // Assign and write avatars using generated user IDs
        for (User u : users) {
            String avatarKey = "AVATAR/" + u.getId() + "/" + u.getUsername() + "_avatar.jpg";
            u.setAvatarKey(avatarKey);
            entityManager.merge(u);
            storageService.upload(avatarKey, SAMPLE_JPEG, "image/jpeg");
        }
        entityManager.flush();

        User u1 = users.get(0);
        User u2 = users.get(1);
        User u3 = users.get(2);
        User u4 = users.get(3);
        User u5 = users.get(4);
        User u6 = users.get(5);

        // 2. Mutual and Asymmetric Follow Relationships using real IDs
        List<long[]> followPairs = List.of(
                // Mutual pairs
                new long[]{u1.getId(), u2.getId()}, new long[]{u2.getId(), u1.getId()},
                new long[]{u1.getId(), u3.getId()}, new long[]{u3.getId(), u1.getId()},
                new long[]{u1.getId(), u4.getId()}, new long[]{u4.getId(), u1.getId()},
                new long[]{u2.getId(), u4.getId()}, new long[]{u4.getId(), u2.getId()},
                new long[]{u3.getId(), u5.getId()}, new long[]{u5.getId(), u3.getId()},
                new long[]{u4.getId(), u6.getId()}, new long[]{u6.getId(), u4.getId()},
                // Asymmetric relations
                new long[]{u2.getId(), u6.getId()},
                new long[]{u5.getId(), u1.getId()},
                new long[]{u5.getId(), u6.getId()},
                new long[]{u6.getId(), u1.getId()},
                new long[]{u4.getId(), u3.getId()},
                new long[]{u4.getId(), u5.getId()}
        );

        for (long[] pair : followPairs) {
            Follow follow = Follow.builder()
                    .followerId(pair[0])
                    .followingId(pair[1])
                    .createdAt(baseTime.plus(6, ChronoUnit.DAYS))
                    .build();
            entityManager.persist(follow);
        }
        entityManager.flush();

        // 3. 24 Realistic Media Items (POST, REEL, STORY)
        record SeedItem(
                Long userId,
                MediaType type,
                MediaKind kind,
                String subPath,
                String thumbSubPath,
                String caption,
                int ageDays,
                boolean isStory
        ) {}

        List<SeedItem> seedItems = List.of(
                // Elena (u1)
                new SeedItem(u1.getId(), MediaType.POST, MediaKind.IMAGE, "museum_island.jpg", "museum_island.jpg", "Morning fog over Museum Island #photography #art #berlin", 14, false),
                new SeedItem(u1.getId(), MediaType.REEL, MediaKind.VIDEO, "film_developing.mp4", "film_thumb.jpg", "Developing 35mm film by hand in home lab #photography #analog #film", 12, false),
                new SeedItem(u1.getId(), MediaType.STORY, MediaKind.IMAGE, "studio_sketch.jpg", "studio_sketch.jpg", "Morning studio sketch #art #sketch", 0, true),
                new SeedItem(u1.getId(), MediaType.POST, MediaKind.IMAGE, "shadow_study.jpg", "shadow_study.jpg", "Architectural geometry in monochrome #photography #minimal #design", 10, false),

                // Marcus (u2)
                new SeedItem(u2.getId(), MediaType.POST, MediaKind.IMAGE, "workspace_setup.jpg", "workspace_setup.jpg", "Clean desk clear mind three monitors #tech #coding #workspace", 13, false),
                new SeedItem(u2.getId(), MediaType.REEL, MediaKind.VIDEO, "local_llm_demo.mp4", "llm_thumb.jpg", "Running local LLMs on custom silicon #tech #ai #coding #developer", 11, false),
                new SeedItem(u2.getId(), MediaType.POST, MediaKind.IMAGE, "custom_keyboard.jpg", "custom_keyboard.jpg", "Custom lubed mechanical switches #tech #gadgets #coding", 8, false),
                new SeedItem(u2.getId(), MediaType.STORY, MediaKind.VIDEO, "night_deploy.mp4", "deploy_thumb.jpg", "Zero downtime deployment complete #coding #devops", 0, true),

                // Sophia (u3)
                new SeedItem(u3.getId(), MediaType.POST, MediaKind.IMAGE, "sourdough_crumb.jpg", "sourdough_crumb.jpg", "72 hour cold ferment open crumb sourdough #food #chef #baking #sourdough", 15, false),
                new SeedItem(u3.getId(), MediaType.REEL, MediaKind.VIDEO, "croissant_laminating.mp4", "croissant_thumb.jpg", "Laminating 27 layers of butter pastry dough #food #chef #pastry #croissant", 9, false),
                new SeedItem(u3.getId(), MediaType.POST, MediaKind.IMAGE, "fresh_tagliatelle.jpg", "fresh_tagliatelle.jpg", "Hand rolled tagliatelle with black truffle butter #food #chef #pasta #italian", 7, false),
                new SeedItem(u3.getId(), MediaType.STORY, MediaKind.IMAGE, "market_haul.jpg", "market_haul.jpg", "Early morning harvest fresh herbs #food #organic", 0, true),

                // Alex (u4)
                new SeedItem(u4.getId(), MediaType.POST, MediaKind.IMAGE, "fitz_roy_sunrise.jpg", "fitz_roy_sunrise.jpg", "Sunrise hitting the Fitz Roy massif in Patagonia #travel #adventure #hiking #mountains", 16, false),
                new SeedItem(u4.getId(), MediaType.REEL, MediaKind.VIDEO, "norway_fjords.mp4", "fjord_thumb.jpg", "Gliding above the Norwegian fjords at golden hour #travel #drone #filmmaking #norway", 8, false),
                new SeedItem(u4.getId(), MediaType.POST, MediaKind.IMAGE, "kyoto_night.jpg", "kyoto_night.jpg", "Rainy evening reflections in Gion Kyoto #travel #japan #streetphotography", 6, false),
                new SeedItem(u4.getId(), MediaType.STORY, MediaKind.VIDEO, "boarding_pass.mp4", "flight_thumb.jpg", "Next stop: Reykjavik #travel #wanderlust", 0, true),

                // Maya (u5)
                new SeedItem(u5.getId(), MediaType.POST, MediaKind.IMAGE, "trail_running.jpg", "trail_running.jpg", "20km alpine trail run before sunrise #fitness #running #trailrun #wellness", 14, false),
                new SeedItem(u5.getId(), MediaType.REEL, MediaKind.VIDEO, "hip_mobility.mp4", "mobility_thumb.jpg", "5 minute morning hip mobility flow #fitness #wellness #mobility #yoga", 7, false),
                new SeedItem(u5.getId(), MediaType.POST, MediaKind.IMAGE, "spirulina_bowl.jpg", "spirulina_bowl.jpg", "Post workout antioxidant nutrient bowl #fitness #nutrition #wellness #healthy", 5, false),
                new SeedItem(u5.getId(), MediaType.STORY, MediaKind.IMAGE, "hydration_reminder.jpg", "hydration_reminder.jpg", "Remember to drink water today #wellness", 0, true),

                // David (u6)
                new SeedItem(u6.getId(), MediaType.POST, MediaKind.IMAGE, "modular_synth_rig.jpg", "modular_synth_rig.jpg", "Patching generative ambient melodies on modular synth #music #synth #producer #ambient", 12, false),
                new SeedItem(u6.getId(), MediaType.REEL, MediaKind.VIDEO, "mpc_jazz_chops.mp4", "mpc_thumb.jpg", "Chopping vintage vinyl jazz chords on MPC #music #producer #hiphop #beats", 6, false),
                new SeedItem(u6.getId(), MediaType.POST, MediaKind.IMAGE, "vintage_pedalboard.jpg", "vintage_pedalboard.jpg", "Analog delay cascading into shimmer reverb #music #guitar #pedalboard #tone", 4, false),
                new SeedItem(u6.getId(), MediaType.STORY, MediaKind.VIDEO, "studio_jam.mp4", "jam_thumb.jpg", "Late night improvisation session #music #jam", 0, true)
        );

        List<Media> createdMediaList = new ArrayList<>();

        for (SeedItem item : seedItems) {
            Instant createdAt = Instant.now().minus(item.ageDays, ChronoUnit.DAYS);
            Instant expiresAt = item.isStory ? Instant.now().plus(24, ChronoUnit.HOURS) : null;
            String r2Key = item.type.name() + "/" + item.userId + "/" + item.subPath;
            String thumbKey = (item.kind == MediaKind.IMAGE) ? r2Key : ("thumbnails/" + item.userId + "/" + item.thumbSubPath);

            Media media = Media.builder()
                    .userId(item.userId)
                    .type(item.type)
                    .mediaKind(item.kind)
                    .r2Key(r2Key)
                    .thumbnailKey(thumbKey)
                    .caption(item.caption)
                    .createdAt(createdAt)
                    .expiresAt(expiresAt)
                    .likeCount(0)
                    .commentCount(0)
                    .shareCount(0)
                    .viewCount(0)
                    .build();

            entityManager.persist(media);
            createdMediaList.add(media);

            // Upload media and thumbnail placeholder binary assets
            if (item.kind == MediaKind.IMAGE) {
                storageService.upload(r2Key, SAMPLE_JPEG, "image/jpeg");
            } else {
                storageService.upload(r2Key, sampleMp4, "video/mp4");
                storageService.upload(thumbKey, SAMPLE_JPEG, "image/jpeg");
            }

            // Extract and persist hashtags
            Matcher matcher = HASHTAG_PATTERN.matcher(item.caption);
            Set<String> distinctTags = new LinkedHashSet<>();
            while (matcher.find() && distinctTags.size() < 10) {
                distinctTags.add(matcher.group(1).toLowerCase());
            }
            for (String tag : distinctTags) {
                entityManager.persist(new MediaTag(media.getId(), tag));
            }
        }
        entityManager.flush();

        // 4. Add Interactions: Likes, Comments, Media Views
        for (Media media : createdMediaList) {
            int likeTarget = (int) (media.getId() % 3) + 2;
            int currentLikes = 0;
            for (User u : users) {
                if (!u.getId().equals(media.getUserId()) && currentLikes < likeTarget) {
                    entityManager.persist(Like.builder()
                            .userId(u.getId())
                            .mediaId(media.getId())
                            .createdAt(media.getCreatedAt().plus(1, ChronoUnit.HOURS))
                            .build());
                    currentLikes++;
                }
            }
            media.setLikeCount(currentLikes);

            // Seed 1 comment
            if (media.getType() != MediaType.STORY) {
                User commenter = users.stream().filter(u -> !u.getId().equals(media.getUserId())).findFirst().orElse(u1);
                entityManager.persist(Comment.builder()
                        .userId(commenter.getId())
                        .mediaId(media.getId())
                        .text("Incredible capture! Absolutely love this perspective.")
                        .createdAt(media.getCreatedAt().plus(2, ChronoUnit.HOURS))
                        .build());
                media.setCommentCount(1);
            }

            // Seed views
            int views = 15 + (int) (media.getId() * 7);
            media.setViewCount(views);
            media.setShareCount(views / 10);

            // Seed a media view event for user interest training
            if (media.getType() == MediaType.REEL) {
                entityManager.persist(MediaView.builder()
                        .userId(u1.getId())
                        .mediaId(media.getId())
                        .watchMs(12000)
                        .durationMs(10000)
                        .completed(true)
                        .viewedAt(media.getCreatedAt().plus(4, ChronoUnit.HOURS))
                        .build());
            }

            entityManager.merge(media);
        }
        entityManager.flush();

        log.info("Database seeding successfully completed with 6 users and {} media items.", createdMediaList.size());
    }
}
