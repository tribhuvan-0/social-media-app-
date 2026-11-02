package com.socialapp.service;

import com.socialapp.config.StorageProperties;
import com.socialapp.exception.NotFoundException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.*;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import software.amazon.awssdk.services.s3.presigner.model.PresignedPutObjectRequest;
import software.amazon.awssdk.services.s3.presigner.model.PutObjectPresignRequest;

import java.io.InputStream;
import java.time.Duration;

@Slf4j
@RequiredArgsConstructor
public class R2StorageService implements StorageService {

    private final S3Client s3Client;
    private final S3Presigner s3Presigner;
    private final StorageProperties properties;

    @Override
    public String generatePresignedUploadUrl(String key, String contentType, long contentLength) {
        PutObjectRequest.Builder objectRequestBuilder = PutObjectRequest.builder()
                .bucket(properties.getR2().getBucket())
                .key(key)
                .contentType(contentType);

        if (contentLength > 0) {
            objectRequestBuilder.contentLength(contentLength);
        }

        PutObjectPresignRequest presignRequest = PutObjectPresignRequest.builder()
                .signatureDuration(Duration.ofMinutes(10))
                .putObjectRequest(objectRequestBuilder.build())
                .build();

        PresignedPutObjectRequest presigned = s3Presigner.presignPutObject(presignRequest);
        return presigned.url().toString();
    }

    @Override
    public void upload(String key, byte[] content, String contentType) {
        PutObjectRequest request = PutObjectRequest.builder()
                .bucket(properties.getR2().getBucket())
                .key(key)
                .contentType(contentType)
                .contentLength((long) content.length)
                .build();
        s3Client.putObject(request, RequestBody.fromBytes(content));
    }

    @Override
    public void upload(String key, InputStream inputStream, long contentLength, String contentType) {
        PutObjectRequest request = PutObjectRequest.builder()
                .bucket(properties.getR2().getBucket())
                .key(key)
                .contentType(contentType)
                .contentLength(contentLength)
                .build();
        s3Client.putObject(request, RequestBody.fromInputStream(inputStream, contentLength));
    }

    @Override
    public InputStream download(String key) {
        try {
            GetObjectRequest request = GetObjectRequest.builder()
                    .bucket(properties.getR2().getBucket())
                    .key(key)
                    .build();
            return s3Client.getObject(request);
        } catch (NoSuchKeyException e) {
            throw new NotFoundException("R2 object not found: " + key);
        }
    }

    @Override
    public void delete(String key) {
        try {
            DeleteObjectRequest request = DeleteObjectRequest.builder()
                    .bucket(properties.getR2().getBucket())
                    .key(key)
                    .build();
            s3Client.deleteObject(request);
        } catch (Exception e) {
            log.warn("Failed to delete R2 object {}: {}", key, e.getMessage());
        }
    }

    @Override
    public String getPublicUrl(String key) {
        if (key == null || key.isBlank()) {
            return null;
        }
        if (key.startsWith("http://") || key.startsWith("https://")) {
            return key;
        }
        String base = properties.getR2().getPublicBaseUrl();
        if (base != null && base.endsWith("/")) {
            base = base.substring(0, base.length() - 1);
        }
        return (base != null ? base : "https://pub-r2.dev") + "/" + key;
    }

    @Override
    public boolean exists(String key) {
        try {
            HeadObjectRequest request = HeadObjectRequest.builder()
                    .bucket(properties.getR2().getBucket())
                    .key(key)
                    .build();
            s3Client.headObject(request);
            return true;
        } catch (NoSuchKeyException e) {
            return false;
        } catch (S3Exception e) {
            if (e.statusCode() == 404) {
                return false;
            }
            throw e;
        }
    }

    @Override
    public long getContentLength(String key) {
        try {
            HeadObjectRequest request = HeadObjectRequest.builder()
                    .bucket(properties.getR2().getBucket())
                    .key(key)
                    .build();
            HeadObjectResponse response = s3Client.headObject(request);
            return response.contentLength();
        } catch (NoSuchKeyException e) {
            throw new NotFoundException("R2 object not found: " + key);
        }
    }
}
