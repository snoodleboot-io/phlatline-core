"""Phlatline SDK — stable plugin interface (v1).

This package is the versioned contract between open-source Phlatline and any
commercial or third-party extension.

Stability rules:
    * Names exported here are versioned. Breaking changes bump the SDK major
      version and live in a new module (phlatline.sdk.v2).
    * The current API lives under phlatline.sdk (== v1). Future v2 will not
      remove v1 — both will coexist during a ≥2-release deprecation window.
    * Internal modules under phlatline.core.* may change without notice.
      Do not import from them.

Example extension:

    from phlatline.sdk import ResultSink, CompletedRun, register_result_sink

    class MyCloudSink(ResultSink):
        name = "my-cloud"
        def emit(self, run: CompletedRun) -> None:
            ...

    register_result_sink(MyCloudSink())
"""
from __future__ import annotations

from phlatline.sdk.interfaces import (
    AlertChannel,
    AuthContextLike,
    Drainable,
    NullAlertChannel,
    NullResultSink,
    NullScheduler,
    ResultSink,
    RunExecutor,
    Scheduler,
    TestExecutor,
)
from phlatline.sdk.models import (
    Alert,
    CompletedRun,
    RequestRecord,
    RunSummary,
    ScheduledJob,
    TargetSpec,
    TestCase,
    TestResult,
)
from phlatline.sdk.registry import (
    clear_registry,
    get_alert_channels,
    get_executor,
    get_result_sinks,
    get_scheduler,
    register_alert_channel,
    register_executor,
    register_result_sink,
    register_scheduler,
)

SDK_VERSION = "1.0"

__all__ = [
    # Interfaces
    "AlertChannel",
    "AuthContextLike",
    "Drainable",
    "ResultSink",
    "RunExecutor",
    "Scheduler",
    "TestExecutor",
    # Null defaults
    "NullAlertChannel",
    "NullResultSink",
    "NullScheduler",
    # Models
    "Alert",
    "CompletedRun",
    "RequestRecord",
    "RunSummary",
    "ScheduledJob",
    "TargetSpec",
    "TestCase",
    "TestResult",
    # Registry
    "clear_registry",
    "get_alert_channels",
    "get_executor",
    "get_result_sinks",
    "get_scheduler",
    "register_alert_channel",
    "register_executor",
    "register_result_sink",
    "register_scheduler",
    # Version
    "SDK_VERSION",
]
