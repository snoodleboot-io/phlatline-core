"""Schemathesis-powered fuzzer.

Pattern: Facade over Schemathesis. If Schemathesis isn't installed, the
facade returns an empty result set with a warning — OSS works without it.
"""
from __future__ import annotations

import time
import warnings
from typing import Any

from phlatline.config.enums import HttpMethod, TestCategory, TestStatus
from phlatline.config.settings import settings
from phlatline.core.redaction import (
    redact_body,
    redact_headers,
    redact_query_params,
    redact_response_preview,
)
from phlatline.sdk.interfaces import AuthContextLike
from phlatline.sdk.models import RequestRecord, TestResult


# Noisy format-override warnings from hypothesis_jsonschema
warnings.filterwarnings("ignore", message="Overriding standard format")

_SCHEMATHESIS_MISSING_MSG = (
    "Schemathesis not installed — fuzzing skipped. "
    "Install with: pip install schemathesis"
)
_SERVER_ERROR_STATUS_THRESHOLD = 500


class FuzzResult:
    """Wrapper return type so callers can distinguish 'skipped' from 'nothing found'."""

    __slots__ = ("results", "warning")

    def __init__(self, results: list[TestResult], warning: str | None) -> None:
        self.results = results
        self.warning = warning


def run_fuzzing(
    schema_source: str,
    base_url: str,
    auth: AuthContextLike,
) -> FuzzResult:
    """Run the fuzzer against a target. Never raises — returns FuzzResult."""
    try:
        import schemathesis  # type: ignore
    except ImportError:
        return FuzzResult([], _SCHEMATHESIS_MISSING_MSG)

    try:
        results = _run_with_schemathesis(schemathesis, schema_source, base_url, auth)
        return FuzzResult(results, None)
    except Exception as e:
        return FuzzResult([], f"Fuzzing failed to start: {type(e).__name__}: {e}")


def _run_with_schemathesis(
    schemathesis: Any,
    schema_source: str,
    base_url: str,
    auth: AuthContextLike,
) -> list[TestResult]:
    schema = _load_schema(schemathesis, schema_source)
    schema.config.update(base_url=base_url, tls_verify=settings.execution.verify_ssl)

    results: list[TestResult] = []
    for op_result in schema.get_all_operations():
        try:
            op = op_result.ok()
        except Exception as e:
            results.append(_skip_result("unknown", f"Could not parse op: {e}"))
            continue
        if op is None:
            continue

        op_id = getattr(op, "operation_id", None) or f"{op.method}_{op.path}"
        samples = _collect_samples(schemathesis, op)

        if not samples:
            results.append(_skip_result(op_id, "Strategy produced no samples"))
            continue

        for i, case in enumerate(samples):
            results.append(_execute_fuzz_case(op, op_id, case, i, auth))

    return results


def _load_schema(schemathesis: Any, source: str) -> Any:
    if source.startswith(("http://", "https://")):
        return schemathesis.openapi.from_url(source)
    return schemathesis.openapi.from_path(source)


def _collect_samples(schemathesis: Any, op: Any) -> list[Any]:
    from hypothesis import HealthCheck, given, settings as hyp_settings  # type: ignore

    strategy = op.as_strategy()
    samples: list[Any] = []

    @given(case=strategy)
    @hyp_settings(
        max_examples=settings.fuzz.examples_per_operation,
        suppress_health_check=list(HealthCheck),
        deadline=None,
        database=None,
    )
    def _collect(case: Any) -> None:
        samples.append(case)

    try:
        _collect()  # type: ignore[call-arg]
    except Exception:
        return []
    return samples


def _execute_fuzz_case(
    op: Any,
    op_id: str,
    case: Any,
    index: int,
    auth: AuthContextLike,
) -> TestResult:
    started = time.perf_counter()
    try:
        merged_headers = {**(case.headers or {}), **auth.headers}
        merged_cookies = {**(case.cookies or {}), **auth.cookies}
        merged_query = {**(case.query or {}), **auth.query_params}

        resp = case.call(
            headers=merged_headers or None,
            cookies=merged_cookies or None,
            params=merged_query or None,
            verify=settings.execution.verify_ssl,
        )
        duration_ms = (time.perf_counter() - started) * 1000
        status = (TestStatus.PASS if resp.status_code < _SERVER_ERROR_STATUS_THRESHOLD
                  else TestStatus.FAIL)
        return TestResult(
            test_id=f"{op_id}::fuzz_{index}",
            category=TestCategory.FUZZ,
            method=_method(case),
            path=case.formatted_path,
            operation_id=op_id,
            summary=f"Fuzz example {index + 1} — {_method(case).value} {op.path}",
            status=status,
            status_code=resp.status_code,
            expected="not 5xx",
            duration_ms=round(duration_ms, 2),
            request=RequestRecord(
                method=_method(case),
                path=case.formatted_path,
                query_params=redact_query_params(dict(merged_query or {})),
                headers=redact_headers(merged_headers),
                body=redact_body(_safe_body(case.body)),
            ),
            response_preview=_safe_preview(resp),
        )
    except Exception as e:
        duration_ms = (time.perf_counter() - started) * 1000
        return TestResult(
            test_id=f"{op_id}::fuzz_{index}",
            category=TestCategory.FUZZ,
            method=_method_fallback(op),
            path=op.path,
            operation_id=op_id,
            summary=f"Fuzz example {index + 1} — request error",
            status=TestStatus.ERROR,
            status_code=None,
            expected="not 5xx",
            duration_ms=round(duration_ms, 2),
            request=RequestRecord(method=_method_fallback(op), path=op.path),
            response_preview="",
            error=f"{type(e).__name__}: {e}",
        )


def _skip_result(op_id: str, msg: str) -> TestResult:
    return TestResult(
        test_id=f"{op_id}::fuzz_skipped",
        category=TestCategory.FUZZ,
        method=HttpMethod.GET,
        path="?",
        operation_id=op_id,
        summary=f"Fuzz skipped for {op_id}",
        status=TestStatus.SKIP,
        status_code=None,
        expected="not 5xx",
        duration_ms=0.0,
        request=RequestRecord(method=HttpMethod.GET, path="?"),
        response_preview="",
        error=msg,
    )


def _method(case: Any) -> HttpMethod:
    try:
        return HttpMethod(str(case.method).upper())
    except ValueError:
        return HttpMethod.GET


def _method_fallback(op: Any) -> HttpMethod:
    try:
        return HttpMethod(str(op.method).upper())
    except (ValueError, AttributeError):
        return HttpMethod.GET


def _safe_preview(resp: Any) -> str:
    limit = settings.fuzz.max_fuzz_body_preview_chars
    try:
        text = resp.text
    except Exception:
        try:
            text = resp.content.decode("utf-8", errors="replace")
        except Exception:
            return ""
    truncated = text[:limit]
    if len(text) > limit:
        truncated = truncated + "…"
    return redact_response_preview(truncated)


def _safe_body(body: Any) -> Any:
    if body is None:
        return None
    if isinstance(body, (dict, list, str, int, float, bool)):
        return body
    try:
        return str(body)
    except Exception:
        return "<unserializable>"
