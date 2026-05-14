"""SequentialExecutor — the OSS default. Pure sync httpx, one request at a time.

Concurrency lives in phlatline-ee's ConcurrentExecutor.

Pattern: Strategy (implements TestExecutor). Also Template Method — subclasses
could override _execute_one without re-implementing the iteration loop.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from phlatline.config.enums import HttpMethod, TestStatus
from phlatline.config.settings import settings
from phlatline.core.redaction import (
    redact_body,
    redact_headers,
    redact_query_params,
    redact_response_preview,
)
from phlatline.sdk.interfaces import AuthContextLike, TestExecutor
from phlatline.sdk.models import RequestRecord, TestCase, TestResult


_STATUS_CODE_DIVISOR = 100  # status_family 2 == 2xx == 200..299


class SequentialExecutor(TestExecutor):
    """Executes cases one at a time using a single synchronous httpx client."""

    name = "sequential"

    def execute(
        self,
        cases: list[TestCase],
        base_url: str,
        auth: AuthContextLike,
    ) -> list[TestResult]:
        exec_settings = settings.execution
        client_kwargs = {
            "base_url": base_url,
            "timeout": exec_settings.request_timeout_s,
            "verify": exec_settings.verify_ssl,
            "follow_redirects": exec_settings.follow_redirects,
        }
        with httpx.Client(**client_kwargs) as client:
            return [self._execute_one(client, case, auth) for case in cases]

    # ---------------------------------------------------------------- helpers

    def _execute_one(
        self,
        client: httpx.Client,
        case: TestCase,
        auth: AuthContextLike,
    ) -> TestResult:
        headers, query, cookies = self._merge_auth(case, auth)
        request_record = self._build_request_record(case, headers, query)

        started = time.perf_counter()
        try:
            resp = client.request(
                case.method.value,
                case.path,
                params=query or None,
                headers=headers or None,
                cookies=cookies or None,
                **self._body_kwargs(case, headers),
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - started) * 1000
            return self._error_result(case, request_record, duration_ms, e)

        duration_ms = (time.perf_counter() - started) * 1000
        return self._success_result(case, request_record, duration_ms, resp)

    @staticmethod
    def _merge_auth(case: TestCase, auth: AuthContextLike
                    ) -> tuple[dict[str, str], dict[str, Any], dict[str, str]]:
        headers = dict(case.headers)
        query = dict(case.query_params)
        cookies: dict[str, str] = {}
        if case.send_auth:
            auth_lowered = {k.lower() for k in auth.headers}
            headers = {k: v for k, v in headers.items() if k.lower() not in auth_lowered}
            headers.update(auth.headers)
            query.update(auth.query_params)
            cookies.update(auth.cookies)
        return headers, query, cookies

    @staticmethod
    def _build_request_record(case: TestCase, headers: dict[str, str],
                              query: dict[str, Any]) -> RequestRecord:
        # Every field that gets persisted into a TestResult (and thus uploaded
        # via the cloud sink) is redacted here. Redaction is one-way; once
        # the RequestRecord is built, secrets are gone for the lifetime of
        # this run.
        return RequestRecord(
            method=case.method,
            path=case.path,
            query_params=redact_query_params(query),
            headers=redact_headers(headers),
            body=redact_body(case.body),
        )

    @staticmethod
    def _body_kwargs(case: TestCase, headers: dict[str, str]) -> dict[str, Any]:
        if case.body is None:
            return {}
        if isinstance(case.body, (dict, list)):
            return {"json": case.body}
        kwargs: dict[str, Any] = {"content": str(case.body).encode()}
        content_type_already_set = any(
            k.lower() == "content-type" for k in headers
        )
        if not content_type_already_set:
            headers["Content-Type"] = "text/plain"
        return kwargs

    # ---------------------------------------------------------------- result building

    @staticmethod
    def _status_matches(code: int, families: tuple[int, ...]) -> bool:
        return any(code // _STATUS_CODE_DIVISOR == fam for fam in families)

    @staticmethod
    def _family_str(families: tuple[int, ...]) -> str:
        return "/".join(f"{f}xx" for f in families)

    @staticmethod
    def _preview(resp: httpx.Response) -> str:
        limit = settings.generation.max_response_preview_chars
        try:
            text = resp.text
        except Exception:
            return "<binary response>"
        truncated = text[:limit]
        if len(text) > limit:
            truncated = truncated + "…"
        # Scan for embedded secrets before returning. Response bodies from
        # auth endpoints commonly echo back tokens; we must not persist them.
        return redact_response_preview(truncated)

    def _success_result(self, case: TestCase, request: RequestRecord,
                        duration_ms: float, resp: httpx.Response) -> TestResult:
        passed = self._status_matches(resp.status_code, case.expected_status_family)
        status = TestStatus.PASS if passed else TestStatus.FAIL
        return TestResult(
            test_id=case.test_id,
            category=case.category,
            method=case.method,
            path=case.path,
            operation_id=case.operation_id,
            summary=case.summary,
            status=status,
            status_code=resp.status_code,
            expected=self._family_str(case.expected_status_family),
            duration_ms=round(duration_ms, 2),
            request=request,
            response_preview=self._preview(resp),
        )

    def _error_result(self, case: TestCase, request: RequestRecord,
                      duration_ms: float, error: Exception) -> TestResult:
        return TestResult(
            test_id=case.test_id,
            category=case.category,
            method=case.method,
            path=case.path,
            operation_id=case.operation_id,
            summary=case.summary,
            status=TestStatus.ERROR,
            status_code=None,
            expected=self._family_str(case.expected_status_family),
            duration_ms=round(duration_ms, 2),
            request=request,
            response_preview="",
            error=f"{type(error).__name__}: {error}",
        )
