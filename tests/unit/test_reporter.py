"""Unit tests for phlatline.report.reporter."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from phlatline import __version__
from phlatline.config.enums import HttpMethod, TestCategory, TestStatus
from phlatline.config.settings import settings
from phlatline.core.project import ProjectSpec, ProjectTargetConfig
from phlatline.core.runner import TargetRun
from phlatline.report.reporter import (
    ReportMeta,
    RunSummary,
    build_meta,
    summarize,
    write_json,
    write_multi_target,
)
from phlatline.sdk.models import RequestRecord, TestResult


# --------------------------------------------------------------------------- #
# Helper
# --------------------------------------------------------------------------- #

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
        ),
        response_preview="ok",
    )


# --------------------------------------------------------------------------- #
# build_meta
# --------------------------------------------------------------------------- #

class TestSuiteBuildMeta:
    def test_returns_report_meta_instance(self):
        meta = build_meta(target="my-api", duration_s=3.14159)
        assert isinstance(meta, ReportMeta)

    def test_target_field_set(self):
        meta = build_meta(target="my-api", duration_s=1.0)
        assert meta.target == "my-api"

    def test_duration_rounded_to_2dp(self):
        meta = build_meta(target="x", duration_s=1.23456)
        assert meta.duration == 1.23

    def test_version_set(self):
        meta = build_meta(target="x", duration_s=1.0)
        assert meta.version == __version__

    def test_timestamp_is_string(self):
        meta = build_meta(target="x", duration_s=1.0)
        assert isinstance(meta.timestamp, str)
        assert len(meta.timestamp) > 0

    def test_fuzz_warning_defaults_to_none(self):
        meta = build_meta(target="x", duration_s=1.0)
        assert meta.fuzz_warning is None

    def test_run_error_defaults_to_none(self):
        meta = build_meta(target="x", duration_s=1.0)
        assert meta.run_error is None

    def test_fuzz_warning_passed_through(self):
        meta = build_meta(target="x", duration_s=1.0, fuzz_warning="watch out")
        assert meta.fuzz_warning == "watch out"

    def test_run_error_passed_through(self):
        meta = build_meta(target="x", duration_s=1.0, run_error="something broke")
        assert meta.run_error == "something broke"


# --------------------------------------------------------------------------- #
# summarize
# --------------------------------------------------------------------------- #

class TestSuiteSummarize:
    def test_empty_list_all_zeros(self):
        s = summarize([])
        assert s.total == 0
        assert s.pass_count == 0
        assert s.fail == 0
        assert s.error == 0
        assert s.skip == 0

    def test_total_equals_len_results(self):
        results = [_make_result(TestStatus.PASS)] * 3
        s = summarize(results)
        assert s.total == 3

    def test_mixed_pass_fail_error(self):
        results = (
            [_make_result(TestStatus.PASS)] * 2
            + [_make_result(TestStatus.FAIL, 400)] * 1
            + [_make_result(TestStatus.ERROR, None)] * 1
        )
        s = summarize(results)
        assert s.pass_count == 2
        assert s.fail == 1
        assert s.error == 1
        assert s.skip == 0
        assert s.total == 4

    def test_skip_counted(self):
        results = [_make_result(TestStatus.SKIP)] * 2
        s = summarize(results)
        assert s.skip == 2
        assert s.total == 2


# --------------------------------------------------------------------------- #
# write_json
# --------------------------------------------------------------------------- #

class TestSuiteWriteJson:
    def test_creates_file(self, tmp_path):
        path = tmp_path / "report.json"
        meta = build_meta(target="x", duration_s=1.0)
        write_json([], path, meta)
        assert path.exists()

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "dir" / "report.json"
        meta = build_meta(target="x", duration_s=1.0)
        write_json([], path, meta)
        assert path.exists()

    def test_output_is_valid_json(self, tmp_path):
        path = tmp_path / "report.json"
        meta = build_meta(target="x", duration_s=1.0)
        write_json([_make_result(TestStatus.PASS)], path, meta)
        data = json.loads(path.read_text())
        assert isinstance(data, dict)

    def test_has_meta_key(self, tmp_path):
        path = tmp_path / "report.json"
        meta = build_meta(target="x", duration_s=1.0)
        write_json([], path, meta)
        data = json.loads(path.read_text())
        assert "meta" in data
        assert isinstance(data["meta"], dict)

    def test_has_summary_key(self, tmp_path):
        path = tmp_path / "report.json"
        meta = build_meta(target="x", duration_s=1.0)
        write_json([], path, meta)
        data = json.loads(path.read_text())
        assert "summary" in data

    def test_has_results_key(self, tmp_path):
        path = tmp_path / "report.json"
        meta = build_meta(target="x", duration_s=1.0)
        write_json([_make_result(TestStatus.PASS)], path, meta)
        data = json.loads(path.read_text())
        assert "results" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) == 1


# --------------------------------------------------------------------------- #
# write_multi_target
# --------------------------------------------------------------------------- #

def _make_project_and_runs(
    target_names: list[str],
) -> tuple[ProjectSpec, list[TargetRun]]:
    targets = [
        ProjectTargetConfig(name=n, schema=f"http://{n}.test/openapi.json")
        for n in target_names
    ]
    spec = ProjectSpec(name="test-project", targets=targets)
    runs = [
        TargetRun(
            target=t,
            base_url=f"http://{t.name}.test",
            results=[_make_result(TestStatus.PASS)],
            duration_s=1.0,
        )
        for t in targets
    ]
    return spec, runs


class TestSuiteWriteMultiTarget:
    @pytest.fixture(autouse=True)
    def _patch_output_dir(self, tmp_path):
        original = settings.report.output_dir
        settings.report.output_dir = tmp_path
        yield
        settings.report.output_dir = original

    def test_creates_per_target_subdir(self, tmp_path):
        spec, runs = _make_project_and_runs(["alpha"])
        write_multi_target(spec, runs, total_duration_s=1.0)
        assert (tmp_path / "alpha").is_dir()

    def test_per_target_json_exists(self, tmp_path):
        spec, runs = _make_project_and_runs(["alpha"])
        write_multi_target(spec, runs, total_duration_s=1.0)
        assert (tmp_path / "alpha" / settings.report.json_report_filename).exists()

    def test_per_target_html_exists(self, tmp_path):
        spec, runs = _make_project_and_runs(["alpha"])
        write_multi_target(spec, runs, total_duration_s=1.0)
        assert (tmp_path / "alpha" / settings.report.html_report_filename).exists()

    def test_combined_html_at_root(self, tmp_path):
        spec, runs = _make_project_and_runs(["alpha"])
        write_multi_target(spec, runs, total_duration_s=1.0)
        assert (tmp_path / settings.report.html_report_filename).exists()

    def test_combined_json_at_root(self, tmp_path):
        spec, runs = _make_project_and_runs(["alpha"])
        write_multi_target(spec, runs, total_duration_s=1.0)
        assert (tmp_path / settings.report.combined_json_filename).exists()

    def test_index_html_at_root(self, tmp_path):
        spec, runs = _make_project_and_runs(["alpha"])
        write_multi_target(spec, runs, total_duration_s=1.0)
        assert (tmp_path / settings.report.project_index_filename).exists()

    def test_returns_multi_target_paths(self, tmp_path):
        spec, runs = _make_project_and_runs(["alpha"])
        paths = write_multi_target(spec, runs, total_duration_s=1.0)
        assert paths.index == tmp_path / settings.report.project_index_filename
        assert paths.combined_html == tmp_path / settings.report.html_report_filename
        assert paths.combined_json == tmp_path / settings.report.combined_json_filename

    def test_errored_run_health_is_errored(self, tmp_path):
        spec, runs = _make_project_and_runs(["alpha"])
        runs[0] = TargetRun(
            target=runs[0].target,
            base_url="http://alpha.test",
            results=[],
            duration_s=0.5,
            error="something went wrong",
        )
        write_multi_target(spec, runs, total_duration_s=1.0)
        combined = json.loads(
            (tmp_path / settings.report.combined_json_filename).read_text()
        )
        assert combined["per_target"][0]["health"] == "errored"

    def test_failing_run_health_is_sick(self, tmp_path):
        spec, runs = _make_project_and_runs(["beta"])
        runs[0] = TargetRun(
            target=runs[0].target,
            base_url="http://beta.test",
            results=[_make_result(TestStatus.FAIL, 400)],
            duration_s=0.5,
        )
        write_multi_target(spec, runs, total_duration_s=1.0)
        combined = json.loads(
            (tmp_path / settings.report.combined_json_filename).read_text()
        )
        assert combined["per_target"][0]["health"] == "sick"

    def test_passing_run_health_is_healthy(self, tmp_path):
        spec, runs = _make_project_and_runs(["gamma"])
        write_multi_target(spec, runs, total_duration_s=1.0)
        combined = json.loads(
            (tmp_path / settings.report.combined_json_filename).read_text()
        )
        assert combined["per_target"][0]["health"] == "healthy"

    def test_combined_summary_aggregates_across_targets(self, tmp_path):
        spec, runs = _make_project_and_runs(["alpha", "beta"])
        # alpha: 1 pass, beta: 1 fail
        runs[1] = TargetRun(
            target=runs[1].target,
            base_url="http://beta.test",
            results=[_make_result(TestStatus.FAIL, 400)],
            duration_s=0.5,
        )
        write_multi_target(spec, runs, total_duration_s=2.0)
        combined = json.loads(
            (tmp_path / settings.report.combined_json_filename).read_text()
        )
        assert combined["summary"]["total"] == 2
        assert combined["summary"]["pass"] == 1
        assert combined["summary"]["fail"] == 1
