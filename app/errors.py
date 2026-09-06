"""Structured API error codes and helpers."""

from __future__ import annotations

from fastapi import HTTPException

AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
SESSION_EXPIRED = "SESSION_EXPIRED"
INVALID_TOKEN = "INVALID_TOKEN"
INVALID_TOKEN_TYPE = "INVALID_TOKEN_TYPE"
USER_NOT_FOUND = "USER_NOT_FOUND"
TENANT_REQUIRED = "TENANT_REQUIRED"
FORBIDDEN = "FORBIDDEN"
CURRENT_DATA_UNAVAILABLE = "CURRENT_DATA_UNAVAILABLE"

_DETAIL_TO_CODE: dict[str, str] = {
    "Not authenticated": AUTHENTICATION_REQUIRED,
    "Invalid token": INVALID_TOKEN,
    "Invalid token type": INVALID_TOKEN_TYPE,
    "User not found": USER_NOT_FOUND,
    "Tenant context required": TENANT_REQUIRED,
    "Not a member of this tenant": FORBIDDEN,
    "Invalid credentials": AUTHENTICATION_REQUIRED,
    "Invalid refresh token": INVALID_TOKEN,
}


def code_from_detail(status_code: int, detail: str) -> str:
    if detail in _DETAIL_TO_CODE:
        return _DETAIL_TO_CODE[detail]
    if status_code == 401:
        return AUTHENTICATION_REQUIRED
    if status_code == 403:
        return FORBIDDEN
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 429:
        return "RATE_LIMITED"
    return "UNKNOWN_ERROR"


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def auth_error(code: str, message: str, status_code: int = 401) -> HTTPException:
    return api_error(status_code, code, message)
