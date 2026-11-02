package com.socialapp.controller;

import com.socialapp.exception.NotFoundException;
import com.socialapp.service.StorageService;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.io.InputStreamResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.HandlerMapping;

import java.io.InputStream;

@Slf4j
@RestController
@RequiredArgsConstructor
@RequestMapping("/api/uploads/local-storage")
public class LocalStorageServeController {

    private final StorageService storageService;

    @PutMapping("/**")
    public ResponseEntity<Void> uploadLocal(HttpServletRequest request) {
        String key = extractKey(request);
        log.debug("Received local storage upload PUT for key: {}", key);
        try {
            long contentLength = request.getContentLengthLong();
            String contentType = request.getContentType();
            if (contentType == null || contentType.isBlank()) {
                contentType = MediaType.APPLICATION_OCTET_STREAM_VALUE;
            }
            try (InputStream in = request.getInputStream()) {
                storageService.upload(key, in, contentLength, contentType);
            }
            return ResponseEntity.ok().build();
        } catch (Exception e) {
            log.error("Failed to upload file locally for key {}: {}", key, e.getMessage(), e);
            throw new RuntimeException("Failed to upload file to local storage", e);
        }
    }

    @GetMapping("/**")
    public ResponseEntity<Resource> serveLocal(HttpServletRequest request) {
        String key = extractKey(request);
        if (!storageService.exists(key)) {
            throw new NotFoundException("Local file not found: " + key);
        }

        long contentLength = storageService.getContentLength(key);
        MediaType mediaType = determineMediaType(key);
        InputStream in = storageService.download(key);
        Resource resource = new InputStreamResource(in);

        return ResponseEntity.ok()
                .contentType(mediaType)
                .contentLength(contentLength)
                .header(HttpHeaders.ACCEPT_RANGES, "bytes")
                .body(resource);
    }

    private String extractKey(HttpServletRequest request) {
        String fullPath = (String) request.getAttribute(HandlerMapping.PATH_WITHIN_HANDLER_MAPPING_ATTRIBUTE);
        String prefix = "/api/uploads/local-storage/";
        if (fullPath != null && fullPath.startsWith(prefix)) {
            return fullPath.substring(prefix.length());
        }
        if (fullPath != null && fullPath.startsWith("/api/uploads/local-storage")) {
            return fullPath.substring("/api/uploads/local-storage".length()).replaceFirst("^/", "");
        }
        return fullPath;
    }

    private MediaType determineMediaType(String key) {
        String lower = key.toLowerCase();
        if (lower.endsWith(".mp4")) {
            return MediaType.valueOf("video/mp4");
        } else if (lower.endsWith(".png")) {
            return MediaType.IMAGE_PNG;
        } else if (lower.endsWith(".jpg") || lower.endsWith(".jpeg")) {
            return MediaType.IMAGE_JPEG;
        } else if (lower.endsWith(".gif")) {
            return MediaType.IMAGE_GIF;
        } else if (lower.endsWith(".webp")) {
            return MediaType.valueOf("image/webp");
        }
        return MediaType.APPLICATION_OCTET_STREAM;
    }
}
