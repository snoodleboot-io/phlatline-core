"""Credential & PII redaction — applied before any captured request/response
leaves the customer's machine.

Rule: nothing in a TestResult leaves the local process with secrets unmasked.
The cloud_agent uploads already-redacted records; the local HTML report
displays already-redacted records. Redaction happens once, at result-build
time in the executor, and is never undone.

What gets redacted:
    * Headers whose name matches a credential pattern
    * Query parameters whose name matches a credential pattern
    * JSON request/response bodies, walked recursively, with
      credential-looking keys masked
    * String values that look like JWTs, bearer tokens, or high-entropy
      secrets (Stripe keys, AWS keys, GitHub tokens, etc.)
"""
from __future__ import annotations

import re
from typing import Any


# --------------------------------------------------------------------------- #
# Patterns
# --------------------------------------------------------------------------- #

_CREDENTIAL_EXACT: frozenset[str] = frozenset({
    "authorization", "cookie", "set-cookie",
    "proxy-authorization", "www-authenticate",
})

_CREDENTIAL_FRAGMENTS: tuple[str, ...] = (
    "token", "api-key", "apikey", "api_key",
    "auth", "secret", "password", "passwd",
    "x-amz-security-token", "x-csrf", "session",
)

_SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\b(?:sk|pk|rk|whsec)_(?:live|test)_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bflt_[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b[a-fA-F0-9]{40,}\b"),  # generic high-entropy hex (sha1+)
)

_MASK_VISIBLE_CHARS = 4
_MASK_SEPARATOR = "…"
_FULLY_MASKED_SHORT = "***"
_FULLY_MASKED_LONG = "***REDACTED***"

_MAX_REDACTION_DEPTH = 32


# --------------------------------------------------------------------------- #
# Predicates
# --------------------------------------------------------------------------- #

def is_credential_name(name: str) -> bool:
    if not name:
        return False
    lowered = name.lower()
    if lowered in _CREDENTIAL_EXACT:
        return True
    return any(fragment in lowered for fragment in _CREDENTIAL_FRAGMENTS)


def looks_like_secret_value(value: str) -> bool:
    if not value or len(value) < 16:
        return False
    return any(p.search(value) for p in _SECRET_VALUE_PATTERNS)


# --------------------------------------------------------------------------- #
# Masking
# --------------------------------------------------------------------------- #

def mask_value(value: str) -> str:
    if not value:
        return value
    if len(value) <= _MASK_VISIBLE_CHARS * 2:
        return _FULLY_MASKED_SHORT
    return f"{value[:_MASK_VISIBLE_CHARS]}{_MASK_SEPARATOR}{value[-_MASK_VISIBLE_CHARS:]}"


def _mask_secrets_in_string(s: str) -> str:
    if not s:
        return s
    result = s
    for pattern in _SECRET_VALUE_PATTERNS:
        result = pattern.sub(_FULLY_MASKED_LONG, result)
    return result


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        name: mask_value(value) if is_credential_name(name) else value
        for name, value in headers.items()
    }


def redact_query_params(params: dict[str, Any]) -> dict[str, Any]:
    return {
        name: (mask_value(str(value)) if is_credential_name(name) else value)
        for name, value in params.items()
    }


def redact_body(body: Any, *, depth: int = 0) -> Any:
    """Walk a JSON-like body; return a new structure with credentials masked."""
    if depth >= _MAX_REDACTION_DEPTH:
        return _FULLY_MASKED_LONG

    if isinstance(body, dict):
        result: dict[Any, Any] = {}
        for k, v in body.items():
            key_is_cred = is_credential_name(str(k))
            if key_is_cred and isinstance(v, (str, int, float)):
                result[k] = mask_value(str(v))
            else:
                result[k] = redact_body(v, depth=depth + 1)
        return result

    if isinstance(body, list):
        return [redact_body(item, depth=depth + 1) for item in body]

    if isinstance(body, str):
        return _mask_secrets_in_string(body)

    return body


def redact_response_preview(text: str) -> str:
    """Scan a response preview for embedded secrets and mask them in place."""
    return _mask_secrets_in_string(text)
