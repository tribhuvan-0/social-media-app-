package com.socialapp.storage;

import com.socialapp.config.StorageProperties;
import com.socialapp.exception.NotFoundException;
import com.socialapp.service.LocalStorageService;
import com.socialapp.util.MediaUrlBuilder;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class LocalStorageServiceTest {

    @TempDir
    Path tempDir;

    private LocalStorageService localStorageService;
    private MediaUrlBuilder mediaUrlBuilder;

    @BeforeEach
    void setUp() {
        StorageProperties properties = new StorageProperties();
        properties.setLocalDir(tempDir.toString());
        properties.setMode("local");

        mediaUrlBuilder = new MediaUrlBuilder("local", "https://pub-r2.dev", "http://localhost:8080", "http://localhost:8080/placeholder-thumb.jpg");
        localStorageService = new LocalStorageService(properties, mediaUrlBuilder);
    }

    @Test
    @DisplayName("Upload byte array, verify exists, size, download content, and delete")
    void testUploadDownloadDeleteByteArray() throws Exception {
        String key = "POST/1/test-image.jpg";
        byte[] content = "test-image-binary-payload".getBytes(StandardCharsets.UTF_8);

        assertThat(localStorageService.exists(key)).isFalse();

        localStorageService.upload(key, content, "image/jpeg");

        assertThat(localStorageService.exists(key)).isTrue();
        assertThat(localStorageService.getContentLength(key)).isEqualTo(content.length);

        try (InputStream in = localStorageService.download(key)) {
            byte[] downloaded = in.readAllBytes();
            assertThat(downloaded).isEqualTo(content);
        }

        localStorageService.delete(key);
        assertThat(localStorageService.exists(key)).isFalse();
    }

    @Test
    @DisplayName("Upload InputStream properly streams to disk")
    void testUploadInputStream() throws Exception {
        String key = "REEL/2/clip.mp4";
        byte[] content = "dummy-video-bytes-stream".getBytes(StandardCharsets.UTF_8);

        localStorageService.upload(key, new ByteArrayInputStream(content), content.length, "video/mp4");

        assertThat(localStorageService.exists(key)).isTrue();
        assertThat(localStorageService.getContentLength(key)).isEqualTo(content.length);

        try (InputStream in = localStorageService.download(key)) {
            assertThat(in.readAllBytes()).isEqualTo(content);
        }
    }

    @Test
    @DisplayName("Path traversal attempts with '..' are blocked and throw SecurityException")
    void testPathTraversalRejection() {
        String illegalKey = "../outside.txt";
        byte[] content = "malicious".getBytes(StandardCharsets.UTF_8);

        assertThatThrownBy(() -> localStorageService.upload(illegalKey, content, "text/plain"))
                .isInstanceOf(SecurityException.class)
                .hasMessageContaining("Directory traversal");
    }

    @Test
    @DisplayName("Download non-existent file throws NotFoundException")
    void testDownloadNonExistentThrows() {
        assertThatThrownBy(() -> localStorageService.download("NON_EXISTENT/file.jpg"))
                .isInstanceOf(NotFoundException.class);
    }

    @Test
    @DisplayName("Generate presigned upload URL returns valid local storage endpoint")
    void testGeneratePresignedUploadUrl() {
        String key = "STORY/3/snap.jpg";
        String url = localStorageService.generatePresignedUploadUrl(key, "image/jpeg", 1024);

        assertThat(url).isEqualTo("http://localhost:8080/api/uploads/local-storage/STORY/3/snap.jpg");
    }

    @Test
    @DisplayName("getPublicUrl returns proper media URL")
    void testGetPublicUrl() {
        String key = "AVATAR/5/profile.png";
        String url = localStorageService.getPublicUrl(key);

        assertThat(url).isEqualTo("http://localhost:8080/api/uploads/local-storage/AVATAR/5/profile.png");
    }
}
