package com.socialapp.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.nio.file.Path;
import java.nio.file.Paths;

@Data
@ConfigurationProperties(prefix = "app.storage")
public class StorageProperties {

    /**
     * Storage mode: "local" or "r2"
     */
    private String mode = "local";

    /**
     * Local storage directory fallback (supports '~' expansion)
     */
    private String localDir = "~/.socialapp/uploads";

    /**
     * Cloudflare R2 properties
     */
    private R2Properties r2 = new R2Properties();

    @Data
    public static class R2Properties {
        private String accountId;
        private String accessKey;
        private String secretKey;
        private String bucket = "socialapp";
        private String publicBaseUrl = "https://pub-r2.dev";
    }

    /**
     * Resolves localDir to an absolute Path, expanding "~" if present.
     */
    public Path resolveLocalDirPath() {
        if (localDir == null || localDir.isBlank()) {
            return Paths.get(System.getProperty("user.home"), ".socialapp", "uploads").toAbsolutePath().normalize();
        }
        String pathStr = localDir.trim();
        if (pathStr.startsWith("~")) {
            pathStr = System.getProperty("user.home") + pathStr.substring(1);
        }
        return Paths.get(pathStr).toAbsolutePath().normalize();
    }
}
