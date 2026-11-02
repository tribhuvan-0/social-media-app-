package com.socialapp.config;

import com.socialapp.service.LocalStorageService;
import com.socialapp.service.R2StorageService;
import com.socialapp.service.StorageService;
import com.socialapp.util.MediaUrlBuilder;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.S3Configuration;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;

import java.net.URI;

@Configuration
@EnableConfigurationProperties(StorageProperties.class)
public class StorageConfig {

    @Bean
    @ConditionalOnProperty(name = "app.storage.mode", havingValue = "r2")
    public S3Client s3Client(StorageProperties properties) {
        var r2 = properties.getR2();
        var endpoint = URI.create("https://" + r2.getAccountId() + ".r2.cloudflarestorage.com");
        var credentials = AwsBasicCredentials.create(
                r2.getAccessKey() != null ? r2.getAccessKey() : "",
                r2.getSecretKey() != null ? r2.getSecretKey() : ""
        );
        return S3Client.builder()
                .endpointOverride(endpoint)
                .region(Region.of("auto"))
                .credentialsProvider(StaticCredentialsProvider.create(credentials))
                .serviceConfiguration(S3Configuration.builder()
                        .pathStyleAccessEnabled(true)
                        .build())
                .build();
    }

    @Bean
    @ConditionalOnProperty(name = "app.storage.mode", havingValue = "r2")
    public S3Presigner s3Presigner(StorageProperties properties) {
        var r2 = properties.getR2();
        var endpoint = URI.create("https://" + r2.getAccountId() + ".r2.cloudflarestorage.com");
        var credentials = AwsBasicCredentials.create(
                r2.getAccessKey() != null ? r2.getAccessKey() : "",
                r2.getSecretKey() != null ? r2.getSecretKey() : ""
        );
        return S3Presigner.builder()
                .endpointOverride(endpoint)
                .region(Region.of("auto"))
                .credentialsProvider(StaticCredentialsProvider.create(credentials))
                .serviceConfiguration(S3Configuration.builder()
                        .pathStyleAccessEnabled(true)
                        .build())
                .build();
    }

    @Bean
    @ConditionalOnProperty(name = "app.storage.mode", havingValue = "r2")
    public StorageService r2StorageService(S3Client s3Client, S3Presigner s3Presigner, StorageProperties properties) {
        return new R2StorageService(s3Client, s3Presigner, properties);
    }

    @Bean
    @ConditionalOnProperty(name = "app.storage.mode", havingValue = "local", matchIfMissing = true)
    public StorageService localStorageService(StorageProperties properties, MediaUrlBuilder mediaUrlBuilder) {
        return new LocalStorageService(properties, mediaUrlBuilder);
    }
}
