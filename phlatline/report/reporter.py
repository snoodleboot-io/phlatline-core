"""Report writing — JSON + HTML output, driven by Pydantic models internally.

Jinja2 templates consume plain dicts (simpler mental model for template
authors), so we serialize models at the render boundary.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field

from phlatline import __version__
from phlatline.config.enums import TargetHealth
from phlatline.config.settings import settings
from phlatline.core.project import ProjectSpec, slugify
from phlatline.core.runner import TargetRun
from phlatline.sdk.models import RunSummary, TestResult


# --------------------------------------------------------------------------- #
# Report metadata
# --------------------------------------------------------------------------- #

_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


class ReportMeta(BaseModel):
    """Metadata displayed in the header of every report."""

    target: str
    timestamp: str
    duration: float
    fuzz_warning: str | None = None
    version: str = __version__
    run_error: str | None = None


def build_meta(target: str, duration_s: float,
               fuzz_warning: str | None = None,
               run_error: str | None = None) -> ReportMeta:
    return ReportMeta(
        target=target,
        timestamp=dt.datetime.now().strftime(_TIMESTAMP_FORMAT),
        duration=round(duration_s, 2),
        fuzz_warning=fuzz_warning,
        run_error=run_error,
    )


# --------------------------------------------------------------------------- #
# Summary helper
# --------------------------------------------------------------------------- #

def summarize(results: list[TestResult]) -> RunSummary:
    summary = RunSummary()
    for r in results:
        match r.status.value:
            case "pass":
                summary.pass_count += 1
            case "fail":
                summary.fail += 1
            case "error":
                summary.error += 1
            case "skip":
                summary.skip += 1
    summary.total = len(results)
    return summary


# --------------------------------------------------------------------------- #
# Jinja environment (lazy singleton)
# --------------------------------------------------------------------------- #

_template_env: Environment | None = None


def _env() -> Environment:
    global _template_env
    if _template_env is None:
        template_dir = Path(__file__).parent / "templates"
        _template_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml", "j2"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _template_env


# --------------------------------------------------------------------------- #
# Serialization at the render boundary
# --------------------------------------------------------------------------- #

def _results_to_dicts(results: list[TestResult]) -> list[dict[str, Any]]:
    return [r.model_dump(mode="json") for r in results]


def _summary_to_dict(summary: RunSummary) -> dict[str, int]:
    # Alias 'pass_count' to 'pass' for template display
    return {
        "total": summary.total,
        "pass": summary.pass_count,
        "fail": summary.fail,
        "error": summary.error,
        "skip": summary.skip,
    }


# --------------------------------------------------------------------------- #
# Single-target writers
# --------------------------------------------------------------------------- #

def write_json(results: list[TestResult], path: Path, meta: ReportMeta) -> None:
    payload = {
        "meta": meta.model_dump(mode="json"),
        "summary": _summary_to_dict(summarize(results)),
        "results": _results_to_dicts(results),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def write_html(results: list[TestResult], path: Path, meta: ReportMeta,
               targets: list[dict[str, str]] | None = None) -> None:
    categories = sorted({r.category.value for r in results})
    template = _env().get_template("report.html.j2")
    rendered = template.render(
        meta=meta.model_dump(mode="json"),
        summary=_summary_to_dict(summarize(results)),
        results=_results_to_dicts(results),
        categories=categories,
        targets=targets or [],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")


# --------------------------------------------------------------------------- #
# Multi-target writer
# --------------------------------------------------------------------------- #

def _health_for(run: TargetRun, summary: RunSummary) -> TargetHealth:
    if run.error:
        return TargetHealth.ERRORED
    if summary.fail > 0 or summary.error > 0:
        return TargetHealth.SICK
    return TargetHealth.HEALTHY


class MultiTargetPaths(BaseModel):
    """Paths written by write_multi_target — returned to the CLI for display."""

    index: Path
    combined_html: Path
    combined_json: Path
    per_target_dir: Path


def write_multi_target(
    project: ProjectSpec,
    runs: list[TargetRun],
    total_duration_s: float,
) -> MultiTargetPaths:
    """Write per-target, combined, and index reports. Returns key paths."""
    out = settings.report.output_dir
    out.mkdir(parents=True, exist_ok=True)

    per_target_summaries: list[dict[str, Any]] = []
    tagged_all_results: list[dict[str, Any]] = []

    for run in runs:
        slug = slugify(run.target.name)
        target_dir = out / slug
        target_dir.mkdir(parents=True, exist_ok=True)

        summary = summarize(run.results)
        meta = build_meta(
            target=run.base_url or run.target.schema_source,
            duration_s=run.duration_s,
            fuzz_warning=run.fuzz_warning,
            run_error=run.error,
        )
        write_json(run.results, target_dir / settings.report.json_report_filename, meta)
        write_html(run.results, target_dir / settings.report.html_report_filename, meta)

        per_target_summaries.append({
            "name": run.target.name,
            "slug": slug,
            "base_url": run.base_url,
            "schema": run.target.schema_source,
            "duration": round(run.duration_s, 2),
            "summary": _summary_to_dict(summary),
            "fuzz_warning": run.fuzz_warning,
            "error": run.error,
            "health": _health_for(run, summary).value,
            "report_path": f"{slug}/{settings.report.html_report_filename}",
        })

        for r in run.results:
            d = r.model_dump(mode="json")
            d["target_name"] = run.target.name
            d["target_slug"] = slug
            tagged_all_results.append(d)

    combined_summary = RunSummary()
    for s in per_target_summaries:
        combined_summary.total += s["summary"]["total"]
        combined_summary.pass_count += s["summary"]["pass"]
        combined_summary.fail += s["summary"]["fail"]
        combined_summary.error += s["summary"]["error"]
        combined_summary.skip += s["summary"]["skip"]

    combined_meta = ReportMeta(
        target=f"{project.name} · {len(runs)} targets",
        timestamp=dt.datetime.now().strftime(_TIMESTAMP_FORMAT),
        duration=round(total_duration_s, 2),
    )

    combined_json_path = out / settings.report.combined_json_filename
    combined_json_path.write_text(
        json.dumps({
            "meta": {**combined_meta.model_dump(mode="json"),
                     "project": project.name, "parallel": project.parallel},
            "summary": _summary_to_dict(combined_summary),
            "per_target": per_target_summaries,
            "results": tagged_all_results,
        }, indent=2, default=str),
        encoding="utf-8",
    )

    categories = sorted({r["category"] for r in tagged_all_results})
    targets_for_filter = [{"name": s["name"], "slug": s["slug"]}
                          for s in per_target_summaries]
    combined_html_path = out / settings.report.html_report_filename
    template = _env().get_template("report.html.j2")
    combined_html_path.write_text(
        template.render(
            meta=combined_meta.model_dump(mode="json"),
            summary=_summary_to_dict(combined_summary),
            results=tagged_all_results,
            categories=categories,
            targets=targets_for_filter,
        ),
        encoding="utf-8",
    )

    index_path = out / settings.report.project_index_filename
    index_template = _env().get_template("index.html.j2")
    index_path.write_text(
        index_template.render(
            project=project.model_dump(mode="json"),
            targets=per_target_summaries,
            combined_summary=_summary_to_dict(combined_summary),
            combined_meta=combined_meta.model_dump(mode="json"),
            version=__version__,
        ),
        encoding="utf-8",
    )

    return MultiTargetPaths(
        index=index_path,
        combined_html=combined_html_path,
        combined_json=combined_json_path,
        per_target_dir=out,
    )
