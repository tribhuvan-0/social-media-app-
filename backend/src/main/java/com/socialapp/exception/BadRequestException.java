package com.socialapp.exception;

import org.springframework.http.HttpStatus;

import java.util.Map;

public class BadRequestException extends ApiException {

    public BadRequestException(String message) {
        super(HttpStatus.BAD_REQUEST, message);
    }

    public BadRequestException(String message, Map<String, String> fieldErrors) {
        super(HttpStatus.BAD_REQUEST, message, fieldErrors);
    }
}
