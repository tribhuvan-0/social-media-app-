package com.socialapp.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "app.recommendation")
public class RecommendationProperties {

    // Interaction Weights
    private double watchedFullyWeight = 2.0;
    private double extraLoopWeight = 1.0;
    private double watchedPartialWeight = 0.5;
    private double skippedWeight = -2.0;
    private double likeWeight = 4.0;
    private double unlikeWeight = -4.0;
    private double commentWeight = 5.0;
    private double shareWeight = 6.0;
    private double followCreatorWeight = 5.0;

    // Thresholds & Decay
    private int coldStartThreshold = 10;
    private double decayFactor = 0.95;
    private double scoreMin = -20.0;
    private double scoreMax = 100.0;
    private double pruneThreshold = 0.5;

    // Pool ratios for normal user (Personalized 40%, Exploration 30%, Popular 30%)
    private double normalPersonalizedRatio = 0.40;
    private double normalExplorationRatio = 0.30;
    private double normalPopularRatio = 0.30;

    // Pool ratios for cold user (Exploration 80%, Popular 20%)
    private double coldExplorationRatio = 0.80;
    private double coldPopularRatio = 0.20;
}
