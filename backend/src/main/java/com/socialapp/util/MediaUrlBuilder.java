package com.socialapp.util;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public class MediaUrlBuilder {

    @Value("${app.storage.mode:local}")
    private String storageMode;

    @Value("${app.storage.r2.public-base-url:https://pub-r2.dev}")
    private String r2PublicBaseUrl;

    @Value("${app.base-url:http://localhost:8080}")
    private String appBaseUrl;

    @Value("${app.placeholder-thumb-url:http://localhost:8080/placeholder-thumb.jpg}")
    private String placeholderThumbUrl;

    public MediaUrlBuilder() {
    }

    public MediaUrlBuilder(String storageMode, String r2PublicBaseUrl, String appBaseUrl, String placeholderThumbUrl) {
        this.storageMode = storageMode;
        this.r2PublicBaseUrl = r2PublicBaseUrl;
        this.appBaseUrl = appBaseUrl;
        this.placeholderThumbUrl = placeholderThumbUrl;
    }

    public String buildMediaUrl(String key) {
        if (key == null || key.isBlank()) {
            return null;
        }
        if (key.startsWith("http://") || key.startsWith("https://")) {
            return key;
        }
        if ("local".equalsIgnoreCase(storageMode)) {
            String base = (appBaseUrl != null && !appBaseUrl.isBlank()) ? appBaseUrl : "http://localhost:8080";
            if (base.endsWith("/")) {
                base = base.substring(0, base.length() - 1);
            }
            return base + "/api/uploads/local-storage/" + key;
        }
        String base = (r2PublicBaseUrl != null && !r2PublicBaseUrl.isBlank()) ? r2PublicBaseUrl : "https://pub-r2.dev";
        if (base.endsWith("/")) {
            base = base.substring(0, base.length() - 1);
        }
        return base + "/" + key;
    }

    public String buildThumbnailUrl(String thumbnailKey) {
        if (thumbnailKey == null || thumbnailKey.isBlank()) {
            return placeholderThumbUrl;
        }
        return buildMediaUrl(thumbnailKey);
    }
}
