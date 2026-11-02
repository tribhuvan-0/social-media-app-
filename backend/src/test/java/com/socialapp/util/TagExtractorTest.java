package com.socialapp.util;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class TagExtractorTest {

    @Test
    @DisplayName("TagExtractor - Extracts lowercased distinct hashtags up to 10")
    void testExtractTags() {
        String caption = "Sunset in Bali! #Travel #sunset #BEACH #travel #wanderlust #photo #explore #ocean #view #fun #extra1 #extra2";
        List<String> tags = TagExtractor.extractTags(caption);

        assertEquals(10, tags.size());
        assertTrue(tags.contains("travel"));
        assertTrue(tags.contains("sunset"));
        assertTrue(tags.contains("beach"));
        assertTrue(tags.contains("wanderlust"));

        // Case insensitive distinct check
        long travelCount = tags.stream().filter("travel"::equals).count();
        assertEquals(1, travelCount);
    }

    @Test
    @DisplayName("TagExtractor - Null or empty input returns empty list")
    void testEmptyCaption() {
        assertTrue(TagExtractor.extractTags(null).isEmpty());
        assertTrue(TagExtractor.extractTags("   ").isEmpty());
        assertTrue(TagExtractor.extractTags("No hashtags here!").isEmpty());
    }
}
