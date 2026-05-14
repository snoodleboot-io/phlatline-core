"""Configuration surface — enums and runtime settings.

Everything categorical, tunable, or environment-driven lives here.
"""
from __future__ import annotations

from phlatline.config.enums import (
    AlertSeverity,
    ApiKeyLocation,
    AuthType,
    HttpMethod,
    OAuth2Flow,
    TargetHealth,
    TestCategory,
    TestStatus,
)
from phlatline.config.settings import (
    CloudSettings,
    ExecutionSettings,
    FuzzSettings,
    GenerationSettings,
    ReportSettings,
    Settings,
    settings,
)

__all__ = [
    # Enums
    "AlertSeverity",
    "ApiKeyLocation",
    "AuthType",
    "HttpMethod",
    "OAuth2Flow",
    "TargetHealth",
    "TestCategory",
    "TestStatus",
    # Settings
    "CloudSettings",
    "ExecutionSettings",
    "FuzzSettings",
    "GenerationSettings",
    "ReportSettings",
    "Settings",
    "settings",
]
