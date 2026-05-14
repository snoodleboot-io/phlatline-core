"""Enumerations — every categorical string value used in the codebase.

Rule: if a value is one-of-a-set (status, category, severity, etc.), it is
defined here as a StrEnum subclass. No string literals for these values
appear anywhere else in the code.

StrEnum (PEP 663 / 3.11+) gives us .value equality with plain strings, so
these serialize cleanly through Pydantic and JSON without extra coercion.
"""
from __future__ import annotations

from enum import StrEnum


class TestStatus(StrEnum):
    """Outcome of a single test case execution."""

    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"


class TestCategory(StrEnum):
    """The kind of assertion a test case embodies."""

    HAPPY = "happy"
    NEGATIVE = "negative"
    AUTH = "auth"
    BOUNDARY = "boundary"
    FUZZ = "fuzz"


class HttpMethod(StrEnum):
    """HTTP methods Phlatline exercises."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class AuthType(StrEnum):
    """Supported authentication schemes."""

    BEARER = "bearer"
    BASIC = "basic"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    CUSTOM = "custom"


class OAuth2Flow(StrEnum):
    """OAuth2 grant flows."""

    CLIENT_CREDENTIALS = "client_credentials"
    PASSWORD = "password"


class ApiKeyLocation(StrEnum):
    """Where an API key is placed in a request."""

    HEADER = "header"
    QUERY = "query"
    COOKIE = "cookie"


class AlertSeverity(StrEnum):
    """Severity of an alert."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class TargetHealth(StrEnum):
    """Summary verdict rendered on the project index page."""

    HEALTHY = "healthy"   # phlatlined — no spikes
    SICK = "sick"         # spiking — has failures
    ERRORED = "errored"   # could not run at all
