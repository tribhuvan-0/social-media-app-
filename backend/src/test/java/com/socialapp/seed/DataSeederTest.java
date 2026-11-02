package com.socialapp.seed;

import com.socialapp.entity.Follow;
import com.socialapp.entity.Media;
import com.socialapp.entity.User;
import com.socialapp.repository.UserRepository;
import com.socialapp.service.StorageService;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.TestPropertySource;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
@TestPropertySource(locations = "classpath:application-test.properties")
class DataSeederTest {

    @Autowired
    private DataSeeder dataSeeder;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private StorageService storageService;

    @Autowired
    private EntityManager entityManager;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void cleanDb() {
        jdbcTemplate.execute("DELETE FROM media_views");
        jdbcTemplate.execute("DELETE FROM story_views");
        jdbcTemplate.execute("DELETE FROM likes");
        jdbcTemplate.execute("DELETE FROM comments");
        jdbcTemplate.execute("DELETE FROM shares");
        jdbcTemplate.execute("DELETE FROM media_tags");
        jdbcTemplate.execute("DELETE FROM media");
        jdbcTemplate.execute("DELETE FROM follows");
        jdbcTemplate.execute("DELETE FROM follow_requests");
        jdbcTemplate.execute("DELETE FROM user_interests");
        jdbcTemplate.execute("DELETE FROM users");
    }

    @Test
    @DisplayName("DataSeeder populates 6 demo users, follows, and 24 media items with files")
    @Transactional
    void testDataSeederPopulatesCompleteCatalog() {
        assertThat(userRepository.count()).isEqualTo(0);

        dataSeeder.run();

        // 1. Verify 6 users
        assertThat(userRepository.count()).isEqualTo(6);

        List<String> expectedUsernames = List.of(
                "elena_v", "marcus_tech", "sophia_chef", "alex_travels", "maya_fitness", "david_music"
        );
        for (String uname : expectedUsernames) {
            User user = userRepository.findByUsername(uname).orElse(null);
            assertThat(user).isNotNull();
            assertThat(user.getBio()).isNotBlank();
            assertThat(user.getAvatarKey()).isNotBlank();
            assertThat(passwordEncoder.matches("Password123!", user.getPasswordHash())).isTrue();
            // Verify avatar exists in storage
            assertThat(storageService.exists(user.getAvatarKey())).isTrue();
        }

        // 2. Verify follows
        List<Follow> follows = entityManager.createQuery("SELECT f FROM Follow f", Follow.class).getResultList();
        assertThat(follows.size()).isGreaterThanOrEqualTo(12);

        // 3. Verify media items
        List<Media> mediaList = entityManager.createQuery("SELECT m FROM Media m", Media.class).getResultList();
        assertThat(mediaList.size()).isEqualTo(24);

        for (Media m : mediaList) {
            assertThat(m.getCaption()).isNotBlank();
            assertThat(m.getR2Key()).isNotBlank();
            // Verify media asset file physically exists in storage
            assertThat(storageService.exists(m.getR2Key())).isTrue();
            if (m.getThumbnailKey() != null) {
                assertThat(storageService.exists(m.getThumbnailKey())).isTrue();
            }
        }

        // 4. Test idempotency: running again when count > 0 skips
        dataSeeder.run();
        assertThat(userRepository.count()).isEqualTo(6);
    }
}
