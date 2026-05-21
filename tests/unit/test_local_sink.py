"""Unit tests for phlatline.report.local_sink."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from phlatline.config.settings import settings
from phlatline.report.local_sink import LocalReportSink
from phlatline.sdk.models import CompletedRun, RunSummary


# --------------------------------------------------------------------------- #
# Helper
# --------------------------------------------------------------------------- #

def _make_completed_run(target_name: str = "my-api") -> CompletedRun:
    return CompletedRun(
        project_name="test",
        target_name=target_name,
        base_url="http://api.test",
        started_at=0.0,
        duration_s=1.0,
        summary=RunSummary(),
        results=[],
        meta={},
    )


# --------------------------------------------------------------------------- #
# Class attribute
# --------------------------------------------------------------------------- #

def test_name_class_attribute():
    assert LocalReportSink.name == "local-report"


# --------------------------------------------------------------------------- #
# output_dir property
# --------------------------------------------------------------------------- #

class TestSuiteOutputDir:
    def test_explicit_path_returned(self, tmp_path):
        sink = LocalReportSink(output_dir=tmp_path)
        assert sink.output_dir == tmp_path

    def test_explicit_path_not_settings(self, tmp_path):
        explicit = tmp_path / "custom"
        sink = LocalReportSink(output_dir=explicit)
        assert sink.output_dir == explicit

    def test_none_falls_back_to_settings(self):
        sink = LocalReportSink(output_dir=None)
        assert sink.output_dir == settings.report.output_dir


# --------------------------------------------------------------------------- #
# emit — success path
# --------------------------------------------------------------------------- #

class TestSuiteEmitSuccess:
    @pytest.fixture(autouse=True)
    def _patch_output_dir(self, tmp_path):
        self._tmp = tmp_path

    def test_creates_target_subdir(self):
        sink = LocalReportSink(output_dir=self._tmp)
        run = _make_completed_run("my-api")
        sink.emit(run)
        assert (self._tmp / "my-api").is_dir()

    def test_creates_json_report(self):
        sink = LocalReportSink(output_dir=self._tmp)
        run = _make_completed_run("my-api")
        sink.emit(run)
        json_path = self._tmp / "my-api" / settings.report.json_report_filename
        assert json_path.exists()

    def test_json_is_valid(self):
        sink = LocalReportSink(output_dir=self._tmp)
        run = _make_completed_run("my-api")
        sink.emit(run)
        json_path = self._tmp / "my-api" / settings.report.json_report_filename
        data = json.loads(json_path.read_text())
        assert isinstance(data, dict)

    def test_json_has_required_keys(self):
        sink = LocalReportSink(output_dir=self._tmp)
        run = _make_completed_run("my-api")
        sink.emit(run)
        json_path = self._tmp / "my-api" / settings.report.json_report_filename
        data = json.loads(json_path.read_text())
        assert "meta" in data
        assert "summary" in data
        assert "results" in data

    def test_creates_html_report(self):
        sink = LocalReportSink(output_dir=self._tmp)
        run = _make_completed_run("my-api")
        sink.emit(run)
        html_path = self._tmp / "my-api" / settings.report.html_report_filename
        assert html_path.exists()

    def test_slug_used_as_subdir(self):
        sink = LocalReportSink(output_dir=self._tmp)
        run = _make_completed_run("My Service API")
        sink.emit(run)
        assert (self._tmp / "my-service-api").is_dir()


# --------------------------------------------------------------------------- #
# emit — error suppression
# --------------------------------------------------------------------------- #

class TestSuiteEmitErrorSuppression:
    def test_write_error_does_not_propagate(self, tmp_path):
        sink = LocalReportSink(output_dir=tmp_path)
        run = _make_completed_run("my-api")
        with patch.object(sink, "_write", side_effect=OSError("disk full")):
            # Must not raise
            sink.emit(run)

    def test_write_error_printed_to_stderr(self, tmp_path, capsys):
        sink = LocalReportSink(output_dir=tmp_path)
        run = _make_completed_run("my-api")
        with patch.object(sink, "_write", side_effect=OSError("disk full")):
            sink.emit(run)
        captured = capsys.readouterr()
        assert "disk full" in captured.err or "OSError" in captured.err
