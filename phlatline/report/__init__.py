"""Phlatline reporting — JSON + HTML output.

Importing this package self-registers LocalReportSink with the SDK registry.
"""
from __future__ import annotations

from phlatline.report.local_sink import LocalReportSink
from phlatline.report.reporter import (
    MultiTargetPaths,
    ReportMeta,
    build_meta,
    summarize,
    write_html,
    write_json,
    write_multi_target,
)
from phlatline.sdk.registry import register_result_sink

# Self-register the OSS default sink
register_result_sink(LocalReportSink())

__all__ = [
    "LocalReportSink",
    "MultiTargetPaths",
    "ReportMeta",
    "build_meta",
    "summarize",
    "write_html",
    "write_json",
    "write_multi_target",
]
