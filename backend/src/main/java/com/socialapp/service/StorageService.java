package com.socialapp.service;

import java.io.InputStream;

public interface StorageService {

    /**
     * Generates a presigned PUT upload URL for direct client upload.
     */
    String generatePresignedUploadUrl(String key, String contentType, long contentLength);

    /**
     * Uploads bytes directly to storage.
     */
    void upload(String key, byte[] content, String contentType);

    /**
     * Uploads an input stream directly to storage.
     */
    void upload(String key, InputStream inputStream, long contentLength, String contentType);

    /**
     * Downloads an object as an InputStream.
     */
    InputStream download(String key);

    /**
     * Deletes an object from storage.
     */
    void delete(String key);

    /**
     * Returns the public access URL for a given key.
     */
    String getPublicUrl(String key);

    /**
     * Checks if an object exists in storage.
     */
    boolean exists(String key);

    /**
     * Returns the content length (size in bytes) of an object in storage.
     */
    long getContentLength(String key);
}
