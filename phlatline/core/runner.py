"""Target runner — orchestrates the load → auth → generate → execute → fuzz flow.

This module is purely sequential. Multi-target parallelism is an EE feature
(EE registers a ConcurrentExecutor and provides a parallel project runner).
"""
from __future__ import annotations

import time

from pydantic import BaseModel, Field, NonNegativeFloat

from phlatline.core.auth import AuthContext, AuthError, build_auth_context
from phlatline.core.fuzzer import run_fuzzing
from phlatline.core.generator import generate_test_cases
from phlatline.core.project import ProjectTargetConfig
from phlatline.core.schema_loader import SchemaLoadError, load_schema, resolve_base_url
from phlatline.sdk.models import TestResult
from phlatline.sdk.registry import get_executor


class TargetRun(BaseModel):
    """The outcome of testing a single target."""

    target: ProjectTargetConfig
    base_url: str
    results: list[TestResult] = Field(default_factory=list)
    duration_s: NonNegativeFloat = 0.0
    fuzz_warning: str | None = None
    error: str | None = None


def run_target(target: ProjectTargetConfig) -> TargetRun:
    """Run the full suite against a single target. Never raises — errors go
    into the TargetRun so one bad target can't abort a multi-target run."""
    started = time.perf_counter()

    try:
        schema = load_schema(target.schema_source)
    except SchemaLoadError as e:
        return _error_run(target, target.base_url or "", started,
                          f"Schema load failed: {e}")

    base_url = resolve_base_url(schema, target.base_url)
    if not base_url:
        return _error_run(target, "", started,
                          "No base URL in schema and no base_url override provided")

    try:
        auth_ctx = build_auth_context(target.auth)
    except AuthError as e:
        return _error_run(target, base_url, started, f"Auth config error: {e}")

    cases = generate_test_cases(schema)

    executor = get_executor()
    results = executor.execute(cases, base_url=base_url, auth=auth_ctx)

    fuzz_warning: str | None = None
    if target.fuzz:
        fuzz = run_fuzzing(target.schema_source, base_url, auth_ctx)
        results.extend(fuzz.results)
        fuzz_warning = fuzz.warning

    return TargetRun(
        target=target,
        base_url=base_url,
        results=results,
        duration_s=time.perf_counter() - started,
        fuzz_warning=fuzz_warning,
        error=None,
    )


def run_many(targets: list[ProjectTargetConfig]) -> list[TargetRun]:
    """Run all targets sequentially. EE can replace this orchestration."""
    return [run_target(t) for t in targets]


def _error_run(target: ProjectTargetConfig, base_url: str, started_at: float,
               error_msg: str) -> TargetRun:
    return TargetRun(
        target=target,
        base_url=base_url,
        results=[],
        duration_s=time.perf_counter() - started_at,
        fuzz_warning=None,
        error=error_msg,
    )


def _to_auth_context_like(ctx: AuthContext) -> AuthContext:
    """AuthContext already satisfies AuthContextLike — kept for clarity."""
    return ctx
