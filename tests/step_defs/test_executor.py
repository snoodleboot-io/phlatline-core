"""Step definitions for tests/features/executor.feature."""
from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx
from pytest_bdd import given, parsers, scenarios, then, when

from phlatline.config.enums import HttpMethod, TestCategory, TestStatus
from phlatline.core.auth import AuthContext
from phlatline.core.sequential_executor import SequentialExecutor
from phlatline.sdk.models import TestCase, TestResult

scenarios("../features/executor.feature")


BASE_URL = "https://api.example.test"


@pytest.fixture
def mock_router():
    """respx router that intercepts httpx calls to the base URL."""
    with respx.mock(base_url=BASE_URL, assert_all_called=False) as router:
        yield router


# --- Given: mock server behavior ---

@given(parsers.parse('a mocked server that returns {code:d} with body {body_json}'), target_fixture="mock_setup")
def _mock_with_body(mock_router, code: int, body_json: str) -> None:
    import json
    mock_router.get("/ping").mock(return_value=httpx.Response(code, json=json.loads(body_json)))
    return None


@given(parsers.parse('a mocked server that returns {code:d}'), target_fixture="mock_setup")
def _mock_simple(mock_router, code: int) -> None:
    mock_router.get("/ping").mock(return_value=httpx.Response(code))
    return None


@given("a mocked server that raises a connection error", target_fixture="mock_setup")
def _mock_connection_error(mock_router) -> None:
    mock_router.get("/ping").mock(side_effect=httpx.ConnectError("boom"))
    return None


# --- Given: TestCase construction ---

@given("a TestCase for GET /ping", target_fixture="case")
def _basic_case() -> TestCase:
    return TestCase(
        test_id="ping::happy",
        category=TestCategory.HAPPY,
        method=HttpMethod.GET,
        path="/ping",
        path_template="/ping",
        operation_id="ping",
        summary="Ping",
        query_params={},
        headers={},
        body=None,
        send_auth=True,
        expected_status_family=(2,),
    )


@given(parsers.parse('a TestCase for GET /ping with Authorization header "{value}"'), target_fixture="case")
def _case_with_auth(value: str) -> TestCase:
    return TestCase(
        test_id="ping::auth",
        category=TestCategory.HAPPY,
        method=HttpMethod.GET,
        path="/ping",
        path_template="/ping",
        operation_id="ping",
        summary="Ping",
        query_params={},
        headers={"Authorization": value},
        body=None,
        send_auth=True,
        expected_status_family=(2,),
    )


@given("a happy-path TestCase for GET /ping", target_fixture="case")
def _happy_case() -> TestCase:
    return TestCase(
        test_id="ping::happy",
        category=TestCategory.HAPPY,
        method=HttpMethod.GET,
        path="/ping",
        path_template="/ping",
        operation_id="ping",
        summary="Ping",
        query_params={},
        headers={},
        body=None,
        send_auth=True,
        expected_status_family=(2,),
    )


# --- When ---

@when("the executor runs the case", target_fixture="result")
def _run(case: TestCase, mock_setup) -> TestResult:
    executor = SequentialExecutor()
    results = executor.execute([case], base_url=BASE_URL, auth=AuthContext())
    return results[0]


# --- Then ---

@then(parsers.parse("the result status_code is {code:d}"))
def _status_code_is(result: TestResult, code: int) -> None:
    assert result.status_code == code


@then(parsers.parse('the result status is "{status}"'))
def _status_is(result: TestResult, status: str) -> None:
    assert str(result.status) == status


@then("the result duration_ms is greater than zero")
def _duration_positive(result: TestResult) -> None:
    assert result.duration_ms > 0


@then("the recorded request Authorization header is masked")
def _auth_masked(result: TestResult) -> None:
    auth = result.request.headers.get("Authorization", "")
    assert auth != ""
    # The real token was "Bearer sk_secret_abcdefghij" — must not appear unmasked
    assert "sk_secret_abcdefghij" not in auth
    # Should contain a mask character
    assert "…" in auth or "*" in auth


@then("the result error message is non-empty")
def _error_nonempty(result: TestResult) -> None:
    assert result.error is not None
    assert len(result.error) > 0
