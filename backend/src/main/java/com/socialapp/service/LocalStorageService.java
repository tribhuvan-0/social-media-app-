package com.socialapp.service;

import com.socialapp.config.StorageProperties;
import com.socialapp.exception.NotFoundException;
import com.socialapp.util.MediaUrlBuilder;
import lombok.extern.slf4j.Slf4j;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.*;

@Slf4j
public class LocalStorageService implements StorageService {

    private final StorageProperties properties;
    private final MediaUrlBuilder mediaUrlBuilder;
    private final Path rootDir;

    public LocalStorageService(StorageProperties properties, MediaUrlBuilder mediaUrlBuilder) {
        this.properties = properties;
        this.mediaUrlBuilder = mediaUrlBuilder;
        this.rootDir = properties.resolveLocalDirPath();
        try {
            Files.createDirectories(this.rootDir);
        } catch (IOException e) {
            log.error("Failed to create local storage directory at {}: {}", this.rootDir, e.getMessage());
        }
    }

    private Path resolveKey(String key) {
        if (key == null || key.isBlank()) {
            throw new IllegalArgumentException("Storage key cannot be null or empty");
        }
        String cleanKey = key.startsWith("/") ? key.substring(1) : key;
        Path resolved = rootDir.resolve(cleanKey).normalize();
        if (!resolved.startsWith(rootDir)) {
            throw new SecurityException("Directory traversal attempt with key: " + key);
        }
        return resolved;
    }

    @Override
    public String generatePresignedUploadUrl(String key, String contentType, long contentLength) {
        String cleanKey = key.startsWith("/") ? key.substring(1) : key;
        return mediaUrlBuilder.buildMediaUrl(cleanKey);
    }

    @Override
    public void upload(String key, byte[] content, String contentType) {
        Path target = resolveKey(key);
        try {
            if (target.getParent() != null) {
                Files.createDirectories(target.getParent());
            }
            Files.write(target, content, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING, StandardOpenOption.WRITE);
            log.debug("Successfully saved {} bytes to {}", content.length, target);
        } catch (IOException e) {
            log.error("Failed to write file to {}: {}", target, e.getMessage(), e);
            throw new RuntimeException("Failed to upload file to local storage", e);
        }
    }

    @Override
    public void upload(String key, InputStream inputStream, long contentLength, String contentType) {
        Path target = resolveKey(key);
        try {
            if (target.getParent() != null) {
                Files.createDirectories(target.getParent());
            }
            Files.copy(inputStream, target, StandardCopyOption.REPLACE_EXISTING);
            log.debug("Successfully streamed file to {}", target);
        } catch (IOException e) {
            log.error("Failed to stream file to {}: {}", target, e.getMessage(), e);
            throw new RuntimeException("Failed to upload file to local storage", e);
        }
    }

    @Override
    public InputStream download(String key) {
        Path target = resolveKey(key);
        if (!Files.isRegularFile(target)) {
            throw new NotFoundException("File not found in local storage: " + key);
        }
        try {
            return Files.newInputStream(target, StandardOpenOption.READ);
        } catch (IOException e) {
            throw new RuntimeException("Failed to read file from local storage: " + key, e);
        }
    }

    @Override
    public void delete(String key) {
        try {
            Path target = resolveKey(key);
            Files.deleteIfExists(target);
            log.debug("Deleted file at {}", target);
        } catch (Exception e) {
            log.warn("Failed to delete file {}: {}", key, e.getMessage());
        }
    }

    @Override
    public String getPublicUrl(String key) {
        String cleanKey = key.startsWith("/") ? key.substring(1) : key;
        return mediaUrlBuilder.buildMediaUrl(cleanKey);
    }

    @Override
    public boolean exists(String key) {
        try {
            Path target = resolveKey(key);
            return Files.isRegularFile(target);
        } catch (Exception e) {
            return false;
        }
    }

    @Override
    public long getContentLength(String key) {
        Path target = resolveKey(key);
        if (!Files.isRegularFile(target)) {
            throw new NotFoundException("File not found: " + key);
        }
        try {
            return Files.size(target);
        } catch (IOException e) {
            throw new RuntimeException("Failed to get content length for " + key, e);
        }
    }
}
