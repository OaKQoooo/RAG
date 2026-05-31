package com.example.damrag.service;

public class RagServiceException extends RuntimeException {
    private final String errorCode;
    private final String userMessage;
    private final String detail;

    public RagServiceException(String errorCode, String userMessage, String detail) {
        super(formatMessage(errorCode, detail));
        this.errorCode = errorCode;
        this.userMessage = userMessage;
        this.detail = detail;
    }

    public RagServiceException(String errorCode, String userMessage, String detail, Throwable cause) {
        super(formatMessage(errorCode, detail), cause);
        this.errorCode = errorCode;
        this.userMessage = userMessage;
        this.detail = detail;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public String getUserMessage() {
        return userMessage;
    }

    public String getDetail() {
        return detail;
    }

    private static String formatMessage(String errorCode, String detail) {
        return "[" + errorCode + "] " + detail;
    }
}
