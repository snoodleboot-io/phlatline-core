"""Unit tests for phlatline.core.runner."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from phlatline.core.auth import AuthContext, AuthError
from phlatline.core.project import ProjectTargetConfig
from phlatline.core.runner import TargetRun, run_many, run_target
from phlatline.core.schema_loader import SchemaLoadError
from phlatline.sdk.models import RequestRecord, TestResult
from phlatline.config.enums import HttpMethod, TestCategory, TestStatus


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _make_target(name: str = "test", fuzz: bool = False) -> ProjectTargetConfig:
    return ProjectTargetConfig(
        name=name,
        schema="http://example.com/openapi.json",
        fuzz=fuzz,
    )


def _make_result(status: TestStatus = TestStatus.PASS) -> TestResult:
    return TestResult(
        test_id="test_1",
        category=TestCategory.HAPPY,
        method=HttpMethod.GET,
        path="/ping",
        operation_id="ping",
        summary="Ping",
        status=status,
        status_code=200,
        expected="2xx",
        duration_ms=10.0,
        request=RequestRecord(
            method=HttpMethod.GET,
            path="/ping",
        ),
    )


_FAKE_SCHEMA = {"openapi": "3.0.0", "info": {"title": "Test", "version": "1.0"}}
_FAKE_BASE_URL = "https://api.example.test"
_FAKE_AUTH = AuthContext()


# --------------------------------------------------------------------------- #
# Error paths — run_target never raises
# --------------------------------------------------------------------------- #

class TestSuiteRunTargetErrors:
    @patch("phlatline.core.runner.load_schema", side_effect=SchemaLoadError("boom"))
    def test_schema_load_error_returns_error_run(self, _mock_load):
        run = run_target(_make_target())
        assert isinstance(run, TargetRun)
        assert run.error is not None
        assert "Schema load failed" in run.error
        assert run.results == []

    @patch("phlatline.core.runner.resolve_base_url", return_value=None)
    @patch("phlatline.core.runner.load_schema", return_value=_FAKE_SCHEMA)
    def test_no_base_url_returns_error_run(self, _mock_load, _mock_resolve):
        run = run_target(_make_target())
        assert isinstance(run, TargetRun)
        assert run.error is not None
        assert "No base URL" in run.error
        assert run.results == []

    @patch(
        "phlatline.core.runner.build_auth_context",
        side_effect=AuthError("bad creds"),
    )
    @patch("phlatline.core.runner.resolve_base_url", return_value=_FAKE_BASE_URL)
    @patch("phlatline.core.runner.load_schema", return_value=_FAKE_SCHEMA)
    def test_auth_error_returns_error_run(self, _mock_load, _mock_resolve, _mock_auth):
        run = run_target(_make_target())
        assert isinstance(run, TargetRun)
        assert run.error is not None
        assert "Auth config error" in run.error
        assert run.results == []


# --------------------------------------------------------------------------- #
# Success path — fuzz disabled
# --------------------------------------------------------------------------- #

class TestSuiteRunTargetSuccess:
    @patch("phlatline.core.runner.generate_test_cases", return_value=[])
    @patch("phlatline.core.runner.get_executor")
    @patch("phlatline.core.runner.build_auth_context", return_value=_FAKE_AUTH)
    @patch("phlatline.core.runner.resolve_base_url", return_value=_FAKE_BASE_URL)
    @patch("phlatline.core.runner.load_schema", return_value=_FAKE_SCHEMA)
    def test_fuzz_false_no_fuzzing_called(
        self,
        _mock_load,
        _mock_resolve,
        _mock_auth,
        mock_get_executor,
        _mock_gen,
    ):
        result_obj = _make_result()
        mock_executor = MagicMock()
        mock_executor.execute.return_value = [result_obj]
        mock_get_executor.return_value = mock_executor

        target = _make_target(fuzz=False)
        with patch("phlatline.core.runner.run_fuzzing") as mock_fuzz:
            run = run_target(target)
            mock_fuzz.assert_not_called()

        assert run.error is None
        assert len(run.results) == 1
        assert run.results[0] is result_obj

    @patch("phlatline.core.runner.generate_test_cases", return_value=[])
    @patch("phlatline.core.runner.get_executor")
    @patch("phlatline.core.runner.build_auth_context", return_value=_FAKE_AUTH)
    @patch("phlatline.core.runner.resolve_base_url", return_value=_FAKE_BASE_URL)
    @patch("phlatline.core.runner.load_schema", return_value=_FAKE_SCHEMA)
    def test_fuzz_true_results_extended(
        self,
        _mock_load,
        _mock_resolve,
        _mock_auth,
        mock_get_executor,
        _mock_gen,
    ):
        executor_result = _make_result(TestStatus.PASS)
        fuzz_result = _make_result(TestStatus.FAIL)

        mock_executor = MagicMock()
        mock_executor.execute.return_value = [executor_result]
        mock_get_executor.return_value = mock_executor

        mock_fuzz_run = MagicMock()
        mock_fuzz_run.results = [fuzz_result]
        mock_fuzz_run.warning = "some warning"

        target = _make_target(fuzz=True)
        with patch("phlatline.core.runner.run_fuzzing", return_value=mock_fuzz_run):
            run = run_target(target)

        assert run.error is None
        assert len(run.results) == 2
        assert run.fuzz_warning == "some warning"

    @patch("phlatline.core.runner.generate_test_cases", return_value=[])
    @patch("phlatline.core.runner.get_executor")
    @patch("phlatline.core.runner.build_auth_context", return_value=_FAKE_AUTH)
    @patch("phlatline.core.runner.resolve_base_url", return_value=_FAKE_BASE_URL)
    @patch("phlatline.core.runner.load_schema", return_value=_FAKE_SCHEMA)
    def test_success_run_has_no_error(
        self,
        _mock_load,
        _mock_resolve,
        _mock_auth,
        mock_get_executor,
        _mock_gen,
    ):
        mock_executor = MagicMock()
        mock_executor.execute.return_value = []
        mock_get_executor.return_value = mock_executor

        target = _make_target(fuzz=False)
        run = run_target(target)
        assert run.error is None
        assert run.base_url == _FAKE_BASE_URL


# --------------------------------------------------------------------------- #
# run_many
# --------------------------------------------------------------------------- #

class TestSuiteRunMany:
    @patch("phlatline.core.runner.generate_test_cases", return_value=[])
    @patch("phlatline.core.runner.get_executor")
    @patch("phlatline.core.runner.build_auth_context", return_value=_FAKE_AUTH)
    @patch("phlatline.core.runner.resolve_base_url", return_value=_FAKE_BASE_URL)
    @patch("phlatline.core.runner.load_schema", return_value=_FAKE_SCHEMA)
    def test_run_many_returns_one_run_per_target(
        self,
        _mock_load,
        _mock_resolve,
        _mock_auth,
        mock_get_executor,
        _mock_gen,
    ):
        mock_executor = MagicMock()
        mock_executor.execute.return_value = []
        mock_get_executor.return_value = mock_executor

        targets = [_make_target("alpha"), _make_target("beta")]
        runs = run_many(targets)

        assert len(runs) == 2

    @patch("phlatline.core.runner.generate_test_cases", return_value=[])
    @patch("phlatline.core.runner.get_executor")
    @patch("phlatline.core.runner.build_auth_context", return_value=_FAKE_AUTH)
    @patch("phlatline.core.runner.resolve_base_url", return_value=_FAKE_BASE_URL)
    @patch("phlatline.core.runner.load_schema", return_value=_FAKE_SCHEMA)
    def test_run_many_each_run_matches_target(
        self,
        _mock_load,
        _mock_resolve,
        _mock_auth,
        mock_get_executor,
        _mock_gen,
    ):
        mock_executor = MagicMock()
        mock_executor.execute.return_value = []
        mock_get_executor.return_value = mock_executor

        targets = [_make_target("alpha"), _make_target("beta")]
        runs = run_many(targets)

        assert runs[0].target.name == "alpha"
        assert runs[1].target.name == "beta"
