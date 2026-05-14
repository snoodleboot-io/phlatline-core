"""LocalReportSink — OSS default ResultSink.

Writes each CompletedRun to the filesystem as HTML + JSON. Registered at
phlatline.report import time, which happens from the CLI module.

Pattern: Adapter — translates the SDK's CompletedRun into arguments the
reporter writers already understand.
"""
from __future__ import annotations

import sys
from pathlib import Path

from phlatline.config.settings import settings
from phlatline.core.project import slugify
from phlatline.report.reporter import _env, _results_to_dicts, _summary_to_dict, build_meta
from phlatline.sdk.interfaces import ResultSink
from phlatline.sdk.models import CompletedRun, TestResult


class LocalReportSink(ResultSink):
    """Writes reports to ReportSettings.output_dir, partitioned by target slug."""

    name = "local-report"

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir_override = output_dir

    @property
    def output_dir(self) -> Path:
        return self._output_dir_override or settings.report.output_dir

    def emit(self, run: CompletedRun) -> None:
        try:
            self._write(run)
        except Exception as e:
            print(f"[phlatline:{self.name}] {type(e).__name__}: {e}",
                  file=sys.stderr)

    def _write(self, run: CompletedRun) -> None:
        slug = slugify(run.target_name)
        target_dir = self.output_dir / slug
        target_dir.mkdir(parents=True, exist_ok=True)

        meta = build_meta(
            target=run.base_url or run.target_name,
            duration_s=run.duration_s,
            fuzz_warning=run.meta.get("fuzz_warning"),
            run_error=run.meta.get("run_error"),
        )

        import json
        (target_dir / settings.report.json_report_filename).write_text(
            json.dumps({
                "meta": meta.model_dump(mode="json"),
                "summary": _summary_to_dict(run.summary),
                "results": _dump_results(run.results),
            }, indent=2, default=str),
            encoding="utf-8",
        )

        categories = sorted({r.category.value for r in run.results})
        template = _env().get_template("report.html.j2")
        rendered = template.render(
            meta=meta.model_dump(mode="json"),
            summary=_summary_to_dict(run.summary),
            results=_dump_results(run.results),
            categories=categories,
            targets=[],
        )
        (target_dir / settings.report.html_report_filename).write_text(
            rendered, encoding="utf-8"
        )


def _dump_results(results: list[TestResult]) -> list[dict]:
    return _results_to_dicts(results)
