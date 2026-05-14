"""Step definitions for tests/features/reporter.feature."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from phlatline.config.enums import HttpMethod, TestCategory, TestStatus
from phlatline.report.reporter import (
    ReportMeta,
    build_meta,
    summarize,
    write_html,
    write_json,
)
from phlatline.sdk.models import RequestRecord, RunSummary, TestResult

scenarios("../features/reporter.feature")


def _make_result(status: TestStatus, code: int | None = 200) -> TestResult:
    return TestResult(
        test_id=f"test_{status.value}",
        category=TestCategory.HAPPY,
        method=HttpMethod.GET,
        path="/ping",
        operation_id="ping",
        summary="Ping",
        status=status,
        status_code=code,
        expected="2xx",
        duration_ms=12.5,
        request=RequestRecord(
            method=HttpMethod.GET,
            path="/ping",
            query_params={},
            headers={},
            body=None,
        ),
        response_preview="ok",
    )


@given(parsers.parse('a list of results with {p:d} passing, {f:d} failing, {e:d} error'), target_fixture="results")
def _mixed_results(p: int, f: int, e: int) -> list[TestResult]:
    return (
        [_make_result(TestStatus.PASS) for _ in range(p)]
        + [_make_result(TestStatus.FAIL, 400) for _ in range(f)]
        + [_make_result(TestStatus.ERROR, None) for _ in range(e)]
    )


@given(parsers.parse('a list of {n:d} passing results'), target_fixture="results")
def _passing_results(n: int) -> list[TestResult]:
    return [_make_result(TestStatus.PASS) for _ in range(n)]


@given(parsers.parse('a list of {n:d} passing result'), target_fixture="results")
def _passing_results_singular(n: int) -> list[TestResult]:
    # Grammar alias for "1 passing result"
    return [_make_result(TestStatus.PASS) for _ in range(n)]


@pytest.fixture
def meta() -> ReportMeta:
    return build_meta(target="https://api.example.test", duration_s=1.0)


@pytest.fixture
def out_path(tmp_path: Path) -> Path:
    return tmp_path / "report"


# --- Summarize ---

@when("summarize is called", target_fixture="summary")
def _summarize(results: list[TestResult]) -> RunSummary:
    return summarize(results)


@then(parsers.parse("the summary total is {n:d}"))
def _total(summary: RunSummary, n: int) -> None:
    assert summary.total == n


@then(parsers.parse("the summary pass_count is {n:d}"))
def _passed(summary: RunSummary, n: int) -> None:
    assert summary.pass_count == n


@then(parsers.parse("the summary fail is {n:d}"))
def _failed(summary: RunSummary, n: int) -> None:
    assert summary.fail == n


@then(parsers.parse("the summary error is {n:d}"))
def _errors(summary: RunSummary, n: int) -> None:
    assert summary.error == n


# --- write_json ---

@when("write_json writes to a temp path", target_fixture="json_path")
def _write_json(results: list[TestResult], out_path: Path, meta: ReportMeta) -> Path:
    path = out_path.with_suffix(".json")
    write_json(results, path, meta)
    return path


@then("the file exists")
def _exists(request: pytest.FixtureRequest) -> None:
    # Look for any path fixture set by the When step
    for name in ("json_path", "html_path"):
        try:
            p = request.getfixturevalue(name)
            assert p.exists(), f"{p} does not exist"
            return
        except Exception:
            continue
    raise AssertionError("No path fixture found")


@then("the file parses as JSON")
def _is_json(json_path: Path) -> None:
    data = json.loads(json_path.read_text())
    assert isinstance(data, dict)


@then(parsers.parse('the parsed JSON has a "{key}" array of length {n:d}'))
def _json_array_len(json_path: Path, key: str, n: int) -> None:
    data = json.loads(json_path.read_text())
    assert isinstance(data[key], list)
    assert len(data[key]) == n


@then(parsers.parse('the parsed JSON has a "{key}" object'))
def _json_has_object(json_path: Path, key: str) -> None:
    data = json.loads(json_path.read_text())
    assert isinstance(data[key], dict)


# --- write_html ---

@when("write_html writes to a temp path", target_fixture="html_path")
def _write_html(results: list[TestResult], out_path: Path, meta: ReportMeta) -> Path:
    path = out_path.with_suffix(".html")
    write_html(results, path, meta)
    return path


@then(parsers.parse('the file contents start with "{prefix}"'))
def _starts_with(html_path: Path, prefix: str) -> None:
    assert html_path.read_text().lstrip().startswith(prefix)


@then(parsers.parse('the file contents contain "{substring}"'))
def _contains(html_path: Path, substring: str) -> None:
    assert substring in html_path.read_text()
