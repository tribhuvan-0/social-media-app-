package com.socialapp.util;

import java.util.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class TagExtractor {

    private static final Pattern HASHTAG_PATTERN = Pattern.compile("#([A-Za-z0-9_]{1,30})");
    private static final int MAX_TAGS = 10;

    private TagExtractor() {
    }

    /**
     * Extracts distinct, lowercased hashtags from text up to MAX_TAGS (10).
     */
    public static List<String> extractTags(String text) {
        if (text == null || text.isBlank()) {
            return Collections.emptyList();
        }

        Matcher matcher = HASHTAG_PATTERN.matcher(text);
        Set<String> distinctTags = new LinkedHashSet<>();
        while (matcher.find() && distinctTags.size() < MAX_TAGS) {
            String tag = matcher.group(1).toLowerCase(Locale.ROOT);
            distinctTags.add(tag);
        }
        return new ArrayList<>(distinctTags);
    }
}
