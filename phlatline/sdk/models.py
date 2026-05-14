"""Domain models for the SDK — the stable wire format between core and plugins.

Rule: every value object is a Pydantic BaseModel. No dataclasses. Fields that
represent categorical choices use the enums from phlatline.config.enums.

These models are the versioned contract. Additive changes are safe within
SDK v1; removals/renames require SDK v2.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat

from phlatline.config.enums import (
    AlertSeverity,
    HttpMethod,
    TestCategory,
    TestStatus,
)


# --------------------------------------------------------------------------- #
# Config models (what a test target looks like to core)
# --------------------------------------------------------------------------- #

class TargetSpec(BaseModel):
    """A single target under test. Either a whole project or one entry in one."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    name: str = Field(min_length=1, description="Human-readable target name.")
    schema_source: str = Field(
        min_length=1,
        description="Path or URL to the OpenAPI schema.",
    )
    base_url: str | None = Field(
        default=None,
        description="Override the base URL from the schema's servers.",
    )
    auth: dict[str, Any] | None = Field(
        default=None,
        description="Auth config block; validated separately by the auth layer.",
    )
    fuzz_enabled: bool = Field(
        default=True,
        description="Whether to run the fuzzer against this target.",
    )


# --------------------------------------------------------------------------- #
# Test case — what's generated from the schema
# --------------------------------------------------------------------------- #

class TestCase(BaseModel):
    """A single test case produced by the generator, ready for an executor."""

    model_config = ConfigDict(frozen=True)

    test_id: str = Field(min_length=1)
    category: TestCategory
    method: HttpMethod
    path: str = Field(description="Path with parameters already substituted.")
    path_template: str = Field(description="Original OpenAPI path template.")
    operation_id: str
    summary: str
    query_params: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    body: Any = None
    send_auth: bool = True
    expected_status_family: tuple[int, ...] = Field(default=(2,))


# --------------------------------------------------------------------------- #
# Test result — what executors produce
# --------------------------------------------------------------------------- #

class RequestRecord(BaseModel):
    """The request that was sent (or would have been, if the sink wants to replay)."""

    method: HttpMethod
    path: str
    query_params: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    body: Any = None


class TestResult(BaseModel):
    """Outcome of executing a TestCase. This is the primary unit consumed by sinks."""

    test_id: str
    category: TestCategory
    method: HttpMethod
    path: str
    operation_id: str
    summary: str
    status: TestStatus
    status_code: int | None = None
    expected: str = Field(description="Human-readable version of the expectation.")
    duration_ms: NonNegativeFloat
    request: RequestRecord
    response_preview: str = ""
    error: str | None = None
    # Target attribution — set when running inside a multi-target project
    target_name: str | None = None
    target_slug: str | None = None


class RunSummary(BaseModel):
    """Aggregated counts across a run's results."""

    total: int = 0
    pass_count: int = Field(default=0, alias="pass")
    fail: int = 0
    error: int = 0
    skip: int = 0

    model_config = ConfigDict(populate_by_name=True)


# --------------------------------------------------------------------------- #
# Completed run — the fan-out payload to sinks
# --------------------------------------------------------------------------- #

class CompletedRun(BaseModel):
    """Everything a ResultSink needs to know about a finished run.

    This is the stable wire format between core and sinks. Fields are
    additive across SDK versions — new optional fields may be added in
    point releases; existing fields never change meaning.
    """

    model_config = ConfigDict(frozen=True)

    project_name: str = Field(min_length=1)
    target_name: str = Field(min_length=1)
    base_url: str
    started_at: NonNegativeFloat = Field(description="Unix timestamp, seconds.")
    duration_s: NonNegativeFloat
    summary: RunSummary
    results: list[TestResult]
    meta: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Alerting
# --------------------------------------------------------------------------- #

class Alert(BaseModel):
    """A notification to deliver through one or more AlertChannels."""

    severity: AlertSeverity
    title: str = Field(min_length=1)
    message: str
    project_name: str
    target_name: str
    report_url: str | None = None
    summary: RunSummary | None = None


# --------------------------------------------------------------------------- #
# Scheduling (EE)
# --------------------------------------------------------------------------- #

class ScheduledJob(BaseModel):
    """A scheduled recurring run. Persistence is the Scheduler's responsibility."""

    model_config = ConfigDict(frozen=True)

    job_id: str = Field(min_length=1)
    project_config_path: str
    cron_expression: str = Field(description="Standard 5-field cron.")
    enabled: bool = True
