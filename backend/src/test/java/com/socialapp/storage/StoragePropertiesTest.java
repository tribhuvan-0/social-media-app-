package com.socialapp.storage;

import com.socialapp.config.StorageProperties;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.nio.file.Paths;

import static org.assertj.core.api.Assertions.assertThat;

class StoragePropertiesTest {

    @Test
    @DisplayName("Default properties are configured as expected")
    void testDefaults() {
        StorageProperties properties = new StorageProperties();
        assertThat(properties.getMode()).isEqualTo("local");
        assertThat(properties.getLocalDir()).isEqualTo("~/.socialapp/uploads");
        assertThat(properties.getR2().getBucket()).isEqualTo("socialapp");
        assertThat(properties.getR2().getPublicBaseUrl()).isEqualTo("https://pub-r2.dev");
    }

    @Test
    @DisplayName("Tilde path in localDir expands to user home")
    void testTildeExpansion() {
        StorageProperties properties = new StorageProperties();
        properties.setLocalDir("~/custom-uploads");

        Path resolved = properties.resolveLocalDirPath();
        Path expected = Paths.get(System.getProperty("user.home"), "custom-uploads").toAbsolutePath().normalize();
        assertThat(resolved).isEqualTo(expected);
    }

    @Test
    @DisplayName("Null or blank localDir defaults to ~/.socialapp/uploads")
    void testBlankLocalDir() {
        StorageProperties properties = new StorageProperties();
        properties.setLocalDir("");

        Path resolved = properties.resolveLocalDirPath();
        Path expected = Paths.get(System.getProperty("user.home"), ".socialapp", "uploads").toAbsolutePath().normalize();
        assertThat(resolved).isEqualTo(expected);
    }

    @Test
    @DisplayName("Relative localDir resolves against working directory")
    void testRelativePath() {
        StorageProperties properties = new StorageProperties();
        properties.setLocalDir("./target/media-test");

        Path resolved = properties.resolveLocalDirPath();
        Path expected = Paths.get("./target/media-test").toAbsolutePath().normalize();
        assertThat(resolved).isEqualTo(expected);
    }
}
