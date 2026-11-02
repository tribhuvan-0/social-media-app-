package com.socialapp.service;

import com.socialapp.entity.Media;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

@Slf4j
@Service
public class FfmpegThumbnailService {

    private final StorageService storageService;
    private final org.springframework.transaction.support.TransactionTemplate transactionTemplate;

    @PersistenceContext
    private EntityManager entityManager;

    @Value("${app.ffmpeg.path:/usr/sbin/ffmpeg}")
    private String ffmpegPath;

    public FfmpegThumbnailService(StorageService storageService,
                                  org.springframework.transaction.support.TransactionTemplate transactionTemplate) {
        this.storageService = storageService;
        this.transactionTemplate = transactionTemplate;
    }

    @Async("thumbnailTaskExecutor")
    public CompletableFuture<Void> generateThumbnailAsync(Long mediaId, String r2Key, Long userId) {
        Path tempDir = null;
        try {
            tempDir = Files.createTempDirectory("thumb-gen-");
            Path videoPath = tempDir.resolve("input.mp4");
            Path thumbPath = tempDir.resolve("thumb.jpg");

            // 1. Download video from storage
            try (InputStream in = storageService.download(r2Key)) {
                Files.copy(in, videoPath);
            }

            // 2. Run FFmpeg at 1.0s scaled to 480px width
            boolean success = runFfmpegCommand(videoPath, thumbPath, "1");
            if (!success || !Files.exists(thumbPath) || Files.size(thumbPath) == 0) {
                log.info("FFmpeg 1.0s extraction produced no output for mediaId {}. Retrying at 0s.", mediaId);
                // Retry at 0s (for short clips)
                success = runFfmpegCommand(videoPath, thumbPath, "0");
            }

            if (success && Files.exists(thumbPath) && Files.size(thumbPath) > 0) {
                byte[] thumbBytes = Files.readAllBytes(thumbPath);
                String thumbKey = "thumbnails/" + userId + "/" + UUID.randomUUID() + ".jpg";
                storageService.upload(thumbKey, thumbBytes, "image/jpeg");
                updateMediaThumbnailKey(mediaId, thumbKey);
                log.info("Successfully generated and saved thumbnail for mediaId {}: {}", mediaId, thumbKey);
            } else {
                log.warn("FFmpeg thumbnail generation failed to produce output file for mediaId {}", mediaId);
            }
        } catch (Exception e) {
            log.error("Error generating FFmpeg thumbnail for mediaId {}: {}", mediaId, e.getMessage(), e);
        } finally {
            cleanupTempDir(tempDir);
        }
        return CompletableFuture.completedFuture(null);
    }

    private String resolveFfmpegExecutable() {
        if (ffmpegPath != null && !ffmpegPath.isBlank()) {
            File f = new File(ffmpegPath);
            if (f.canExecute()) {
                return ffmpegPath;
            }
            if ("ffmpeg".equalsIgnoreCase(ffmpegPath)) {
                if (new File("/usr/sbin/ffmpeg").canExecute()) {
                    return "/usr/sbin/ffmpeg";
                }
                if (new File("/usr/bin/ffmpeg").canExecute()) {
                    return "/usr/bin/ffmpeg";
                }
            }
            return ffmpegPath;
        }
        if (new File("/usr/sbin/ffmpeg").canExecute()) {
            return "/usr/sbin/ffmpeg";
        }
        return "ffmpeg";
    }

    private boolean runFfmpegCommand(Path videoPath, Path thumbPath, String seekSeconds) {
        try {
            String executable = resolveFfmpegExecutable();
            List<String> command = List.of(
                    executable,
                    "-y",
                    "-ss", seekSeconds,
                    "-i", videoPath.toAbsolutePath().toString(),
                    "-vframes", "1",
                    "-vf", "scale=480:-2",
                    thumbPath.toAbsolutePath().toString()
            );

            ProcessBuilder processBuilder = new ProcessBuilder(command);
            Process process = processBuilder.start();

            // Drain stdout and stderr asynchronously to prevent buffer deadlocks
            CompletableFuture<Void> outDrain = CompletableFuture.runAsync(() -> {
                try (InputStream is = process.getInputStream()) {
                    is.transferTo(OutputStream.nullOutputStream());
                } catch (IOException ignored) {}
            });
            CompletableFuture<Void> errDrain = CompletableFuture.runAsync(() -> {
                try (InputStream es = process.getErrorStream()) {
                    es.transferTo(OutputStream.nullOutputStream());
                } catch (IOException ignored) {}
            });

            boolean finished = process.waitFor(30, TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                log.warn("FFmpeg command timed out after 30 seconds for {}", videoPath);
                return false;
            }

            outDrain.join();
            errDrain.join();

            return process.exitValue() == 0;
        } catch (Exception e) {
            log.warn("FFmpeg execution error: {}", e.getMessage());
            return false;
        }
    }

    public void updateMediaThumbnailKey(Long mediaId, String thumbnailKey) {
        try {
            transactionTemplate.executeWithoutResult(status -> {
                Media media = entityManager.find(Media.class, mediaId);
                if (media != null) {
                    media.setThumbnailKey(thumbnailKey);
                    entityManager.merge(media);
                }
            });
        } catch (Exception e) {
            log.error("Failed to update thumbnail_key on mediaId {}: {}", mediaId, e.getMessage(), e);
        }
    }

    private void cleanupTempDir(Path tempDir) {
        if (tempDir == null) return;
        try (var stream = Files.walk(tempDir)) {
            stream.sorted((a, b) -> b.compareTo(a))
                    .forEach(path -> {
                        try {
                            Files.deleteIfExists(path);
                        } catch (IOException ignored) {}
                    });
        } catch (Exception e) {
            log.debug("Failed to completely clean up temp dir {}: {}", tempDir, e.getMessage());
        }
    }
}
