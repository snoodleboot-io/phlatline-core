"""Unit tests for phlatline.cli helpers and CLI commands."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
import yaml

from phlatline import __version__
from phlatline.cli import (
    _emit_to_sinks,
    _drain_all,
    _format_summary_line,
    _load_auth_config,
    _run_to_completed,
    cli,
    main,
)
from phlatline.config.enums import HttpMethod, TestCategory, TestStatus
from phlatline.core.project import ProjectSpec, ProjectTargetConfig
from phlatline.core.runner import TargetRun
from phlatline.report.reporter import MultiTargetPaths
from phlatline.sdk.models import CompletedRun, RequestRecord, RunSummary, TestResult
from phlatline.sdk.registry import (
    clear_registry,
    register_alert_channel,
    register_result_sink,
)


@pytest.fixture(autouse=True)
def _reset_registry():
    """Clear registry before and after each test to prevent sink bleed."""
    clear_registry()
    yield
    clear_registry()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _make_test_result(status: TestStatus = TestStatus.PASS) -> TestResult:
    return TestResult(
        test_id="t1",
        category=TestCategory.HAPPY,
        method=HttpMethod.GET,
        path="/ping",
        operation_id="ping",
        summary="Ping the API",
        status=status,
        status_code=200,
        expected="2xx",
        duration_ms=5.0,
        request=RequestRecord(
            method=HttpMethod.GET,
            path="/ping",
        ),
        response_preview="ok",
    )


def _make_target_run(results: list[TestResult] | None = None):
    """Return a mock TargetRun with sensible defaults."""
    from phlatline.core.runner import TargetRun
    from phlatline.core.project import ProjectTargetConfig

    target = ProjectTargetConfig(
        name="my-target",
        schema="http://localhost/openapi.json",
        base_url="http://localhost",
    )
    return TargetRun(
        target=target,
        base_url="http://localhost",
        results=results or [],
        duration_s=1.5,
    )


# --------------------------------------------------------------------------- #
# _load_auth_config
# --------------------------------------------------------------------------- #

class TestSuiteLoadAuthConfig:
    def test_none_path_returns_none(self):
        from phlatline.cli import _load_auth_config
        assert _load_auth_config(None) is None

    def test_nonexistent_path_raises_click_exception(self):
        from phlatline.cli import _load_auth_config
        with pytest.raises(click.ClickException) as exc_info:
            _load_auth_config("nonexistent_path.yaml")
        assert "Config file not found" in str(exc_info.value.format_message())

    def test_yaml_file_with_auth_returns_auth_dict(self, tmp_path):
        from phlatline.cli import _load_auth_config
        config = {"auth": {"type": "bearer", "token": "abc"}}
        p = tmp_path / "auth.yaml"
        p.write_text(yaml.dump(config), encoding="utf-8")
        result = _load_auth_config(str(p))
        assert result == {"type": "bearer", "token": "abc"}

    def test_yaml_file_without_auth_returns_none(self, tmp_path):
        from phlatline.cli import _load_auth_config
        config = {"other_key": "value"}
        p = tmp_path / "config.yaml"
        p.write_text(yaml.dump(config), encoding="utf-8")
        assert _load_auth_config(str(p)) is None

    def test_json_file_with_auth_returns_auth_dict(self, tmp_path):
        from phlatline.cli import _load_auth_config
        config = {"auth": {"type": "apikey", "header": "X-API-Key", "key": "secret"}}
        p = tmp_path / "auth.json"
        p.write_text(json.dumps(config), encoding="utf-8")
        result = _load_auth_config(str(p))
        assert result == {"type": "apikey", "header": "X-API-Key", "key": "secret"}


# --------------------------------------------------------------------------- #
# _format_summary_line
# --------------------------------------------------------------------------- #

class TestSuiteFormatSummaryLine:
    def test_all_values_present_in_output(self):
        summary = {"total": 10, "pass": 8, "fail": 1, "error": 1, "skip": 0}
        line = _format_summary_line(summary)
        assert "10" in line
        assert "8" in line
        assert "1" in line
        assert "0" in line
        # Check the label names are present too
        assert "TOTAL" in line
        assert "PASS" in line
        assert "FAIL" in line
        assert "ERROR" in line
        assert "SKIP" in line


# --------------------------------------------------------------------------- #
# _run_to_completed
# --------------------------------------------------------------------------- #

class TestSuiteRunToCompleted:
    def test_returns_completed_run_with_correct_fields(self):
        results = [_make_test_result(TestStatus.PASS), _make_test_result(TestStatus.FAIL)]
        run = _make_target_run(results)
        completed = _run_to_completed(run, project_name="my-project")

        assert isinstance(completed, CompletedRun)
        assert completed.project_name == "my-project"
        assert completed.target_name == run.target.name
        assert completed.base_url == run.base_url

    def test_summary_total_equals_result_count(self):
        results = [_make_test_result() for _ in range(5)]
        run = _make_target_run(results)
        completed = _run_to_completed(run, project_name="p")
        assert completed.summary.total == 5


# --------------------------------------------------------------------------- #
# _emit_to_sinks
# --------------------------------------------------------------------------- #

class TestSuiteEmitToSinks:
    def test_registered_sink_emit_is_called(self):
        mock_sink = MagicMock()
        mock_sink.name = "mock-sink"
        register_result_sink(mock_sink)

        results = [_make_test_result()]
        run = _make_target_run(results)
        completed = _run_to_completed(run, project_name="p")
        _emit_to_sinks(completed)

        mock_sink.emit.assert_called_once_with(completed)

    def test_sink_emit_exception_is_caught_and_logged_to_stderr(self, capsys):
        mock_sink = MagicMock()
        mock_sink.name = "error-sink"
        mock_sink.emit.side_effect = RuntimeError("sink explosion")
        register_result_sink(mock_sink)

        results = [_make_test_result()]
        run = _make_target_run(results)
        completed = _run_to_completed(run, project_name="p")

        # Should NOT propagate
        _emit_to_sinks(completed)

        captured = capsys.readouterr()
        assert "error-sink" in captured.err
        assert "RuntimeError" in captured.err


# --------------------------------------------------------------------------- #
# _drain_all
# --------------------------------------------------------------------------- #

class TestSuiteDrainAll:
    def test_sink_and_channel_drain_called(self):
        mock_sink = MagicMock()
        mock_sink.name = "drain-sink"
        mock_ch = MagicMock()
        mock_ch.name = "drain-channel"

        register_result_sink(mock_sink)
        register_alert_channel(mock_ch)

        _drain_all()

        mock_sink.drain.assert_called_once()
        mock_ch.drain.assert_called_once()

    def test_sink_drain_exception_is_caught(self, capsys):
        mock_sink = MagicMock()
        mock_sink.name = "leaky-sink"
        mock_sink.drain.side_effect = IOError("network gone")
        register_result_sink(mock_sink)

        # Should NOT propagate
        _drain_all()

        captured = capsys.readouterr()
        assert "leaky-sink" in captured.err
        assert "OSError" in captured.err


# --------------------------------------------------------------------------- #
# main() entry point
# --------------------------------------------------------------------------- #

class TestSuiteMainEntryPoint:
    def test_version_flag_exits_zero(self):
        exit_code = main(["--version"])
        assert exit_code == 0

    def test_scan_help_exits_zero(self):
        exit_code = main(["scan", "--help"])
        assert exit_code == 0

    def test_legacy_url_injects_scan(self):
        """main() with a bare URL (no subcommand) should inject 'scan'."""
        # We verify by patching cli.main and asserting 'scan' is prepended.
        injected_args = []

        def capture_args(args, standalone_mode):
            injected_args.extend(args)
            raise click.exceptions.Exit(0)

        with patch("phlatline.cli.cli.main", side_effect=capture_args):
            main(["http://example.com/openapi.json"])

        assert injected_args[0] == "scan"
        assert "http://example.com/openapi.json" in injected_args

    def test_known_subcommand_not_injected(self):
        """'scan' already in argv should NOT result in ['scan', 'scan', ...]."""
        injected_args = []

        def capture_args(args, standalone_mode):
            injected_args.extend(args)
            raise click.exceptions.Exit(0)

        with patch("phlatline.cli.cli.main", side_effect=capture_args):
            main(["scan", "--help"])

        assert injected_args.count("scan") == 1


# --------------------------------------------------------------------------- #
# cli group — no subcommand
# --------------------------------------------------------------------------- #

class TestSuiteCliGroup:
    def test_no_banner_flag_exits_zero_and_shows_subcommands(self, cli_runner):
        result = cli_runner.invoke(cli, ["--no-banner"])
        assert result.exit_code == 0
        assert "scan" in result.output
        assert "project" in result.output


# --------------------------------------------------------------------------- #
# scan command
# --------------------------------------------------------------------------- #

def _make_target_run(results=None, error=None) -> TargetRun:
    target = ProjectTargetConfig(name="phlatline-run", schema="http://api.test/openapi.json")
    return TargetRun(
        target=target,
        base_url="http://api.test",
        results=results or [],
        duration_s=0.1,
        error=error,
    )


class TestSuiteScanCommand:
    def test_scan_success_exits_zero(self, cli_runner):
        mock_run = _make_target_run()
        with patch("phlatline.cli.run_target", return_value=mock_run):
            result = cli_runner.invoke(cli, ["--no-banner", "scan", "http://api.test/openapi.json"])
        assert result.exit_code == 0

    def test_scan_prints_base_url(self, cli_runner):
        mock_run = _make_target_run()
        with patch("phlatline.cli.run_target", return_value=mock_run):
            result = cli_runner.invoke(cli, ["--no-banner", "scan", "http://api.test/openapi.json"])
        assert "http://api.test" in result.output

    def test_scan_run_error_exits_2(self, cli_runner):
        mock_run = _make_target_run(error="Schema load failed: file not found")
        with patch("phlatline.cli.run_target", return_value=mock_run):
            result = cli_runner.invoke(cli, ["--no-banner", "scan", "http://api.test/openapi.json"])
        assert result.exit_code == 2

    def test_scan_failing_results_exits_1(self, cli_runner):
        fail_result = _make_test_result(TestStatus.FAIL)
        mock_run = _make_target_run(results=[fail_result])
        with patch("phlatline.cli.run_target", return_value=mock_run):
            result = cli_runner.invoke(cli, ["--no-banner", "scan", "http://api.test/openapi.json"])
        assert result.exit_code == 1

    def test_scan_fuzz_warning_shown(self, cli_runner):
        mock_run = _make_target_run()
        mock_run = mock_run.model_copy(update={"fuzz_warning": "fuzz coverage low"})
        with patch("phlatline.cli.run_target", return_value=mock_run):
            result = cli_runner.invoke(
                cli, ["--no-banner", "scan", "http://api.test/openapi.json"],
            )
        assert "fuzz coverage low" in result.output

    def test_scan_no_fuzz_flag_propagated(self, cli_runner):
        mock_run = _make_target_run()
        with patch("phlatline.cli.run_target", return_value=mock_run) as mock_rt:
            cli_runner.invoke(
                cli, ["--no-banner", "scan", "http://api.test/openapi.json", "--no-fuzz"]
            )
        called_target = mock_rt.call_args[0][0]
        assert called_target.fuzz is False


# --------------------------------------------------------------------------- #
# project command
# --------------------------------------------------------------------------- #

class TestSuiteProjectCommand:
    def _make_spec(self) -> ProjectSpec:
        return ProjectSpec(
            name="test-project",
            targets=[
                ProjectTargetConfig(name="svc-a", schema="http://a.test/openapi.json"),
            ],
        )

    def _make_multi_paths(self, tmp_path: Path) -> MultiTargetPaths:
        return MultiTargetPaths(
            index=tmp_path / "index.html",
            combined_html=tmp_path / "report.html",
            combined_json=tmp_path / "combined.json",
            per_target_dir=tmp_path,
        )

    def _project_file(self, tmp_path: Path) -> Path:
        # Click validates exists=True before the handler runs, so create a real file.
        p = tmp_path / "project.yaml"
        p.write_text("name: test-project\ntargets: []\n", encoding="utf-8")
        return p

    def test_project_success_exits_zero(self, cli_runner, tmp_path):
        spec = self._make_spec()
        mock_run = _make_target_run()
        paths = self._make_multi_paths(tmp_path)
        with (
            patch("phlatline.cli.load_project", return_value=spec),
            patch("phlatline.cli.run_target", return_value=mock_run),
            patch("phlatline.cli.write_multi_target", return_value=paths),
        ):
            result = cli_runner.invoke(
                cli, ["--no-banner", "project", str(self._project_file(tmp_path))]
            )
        assert result.exit_code == 0

    def test_project_load_error_exits_2(self, cli_runner, tmp_path):
        from phlatline.core.project import ProjectLoadError
        with patch("phlatline.cli.load_project", side_effect=ProjectLoadError("bad config")):
            result = cli_runner.invoke(
                cli, ["--no-banner", "project", str(self._project_file(tmp_path))]
            )
        assert result.exit_code == 2

    def test_project_parallel_and_sequential_flags_mutually_exclusive(self, cli_runner, tmp_path):
        spec = self._make_spec()
        with patch("phlatline.cli.load_project", return_value=spec):
            result = cli_runner.invoke(
                cli,
                ["--no-banner", "project", str(self._project_file(tmp_path)),
                 "--parallel", "--sequential"],
            )
        assert result.exit_code == 2

    def test_project_shows_project_name(self, cli_runner, tmp_path):
        spec = self._make_spec()
        mock_run = _make_target_run()
        paths = self._make_multi_paths(tmp_path)
        with (
            patch("phlatline.cli.load_project", return_value=spec),
            patch("phlatline.cli.run_target", return_value=mock_run),
            patch("phlatline.cli.write_multi_target", return_value=paths),
        ):
            result = cli_runner.invoke(
                cli, ["--no-banner", "project", str(self._project_file(tmp_path))]
            )
        assert "test-project" in result.output

    def test_project_failing_run_exits_1(self, cli_runner, tmp_path):
        spec = self._make_spec()
        fail_result = _make_test_result(TestStatus.FAIL)
        mock_run = _make_target_run(results=[fail_result])
        paths = self._make_multi_paths(tmp_path)
        with (
            patch("phlatline.cli.load_project", return_value=spec),
            patch("phlatline.cli.run_target", return_value=mock_run),
            patch("phlatline.cli.write_multi_target", return_value=paths),
        ):
            result = cli_runner.invoke(
                cli, ["--no-banner", "project", str(self._project_file(tmp_path))]
            )
        assert result.exit_code == 1

    def test_project_sequential_flag(self, cli_runner, tmp_path):
        spec = self._make_spec()
        mock_run = _make_target_run()
        paths = self._make_multi_paths(tmp_path)
        with (
            patch("phlatline.cli.load_project", return_value=spec),
            patch("phlatline.cli.run_target", return_value=mock_run),
            patch("phlatline.cli.write_multi_target", return_value=paths),
        ):
            result = cli_runner.invoke(
                cli, ["--no-banner", "project", str(self._project_file(tmp_path)), "--sequential"]
            )
        assert result.exit_code == 0

    def test_project_max_parallel_flag(self, cli_runner, tmp_path):
        spec = self._make_spec()
        mock_run = _make_target_run()
        paths = self._make_multi_paths(tmp_path)
        with (
            patch("phlatline.cli.load_project", return_value=spec),
            patch("phlatline.cli.run_target", return_value=mock_run),
            patch("phlatline.cli.write_multi_target", return_value=paths),
        ):
            result = cli_runner.invoke(
                cli,
                ["--no-banner", "project", str(self._project_file(tmp_path)), "--max-parallel", "2"],
            )
        assert result.exit_code == 0

    def test_project_errored_run_exits_1(self, cli_runner, tmp_path):
        spec = self._make_spec()
        mock_run = _make_target_run(error="connection refused")
        paths = self._make_multi_paths(tmp_path)
        with (
            patch("phlatline.cli.load_project", return_value=spec),
            patch("phlatline.cli.run_target", return_value=mock_run),
            patch("phlatline.cli.write_multi_target", return_value=paths),
        ):
            result = cli_runner.invoke(
                cli, ["--no-banner", "project", str(self._project_file(tmp_path))]
            )
        assert result.exit_code == 1


# --------------------------------------------------------------------------- #
# scan command — option branches
# --------------------------------------------------------------------------- #

class TestSuiteScanOptions:
    def test_fuzz_examples_option(self, cli_runner):
        mock_run = _make_target_run()
        with patch("phlatline.cli.run_target", return_value=mock_run):
            result = cli_runner.invoke(
                cli,
                ["--no-banner", "scan", "http://api.test/openapi.json", "--fuzz-examples", "5"],
            )
        assert result.exit_code == 0

    def test_no_verify_ssl_option(self, cli_runner):
        mock_run = _make_target_run()
        with patch("phlatline.cli.run_target", return_value=mock_run):
            result = cli_runner.invoke(
                cli,
                ["--no-banner", "scan", "http://api.test/openapi.json", "--no-verify-ssl"],
            )
        assert result.exit_code == 0
