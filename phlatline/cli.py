"""Phlatline CLI — Click-based.

Two subcommands:

    phlatline scan SCHEMA [options]       # single-target
    phlatline project FILE [options]      # multi-target

Legacy `phlatline SCHEMA` invocation works via a fallback in main() so
existing integrations don't break.
"""
from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path
from typing import Any

import click
import yaml
from pydantic import BaseModel

from phlatline import __version__
from phlatline.config.settings import settings
from phlatline.core.project import (
    ProjectLoadError,
    ProjectTargetConfig,
    load_project,
)
from phlatline.core.runner import TargetRun, run_target
from phlatline.report.reporter import (
    build_meta,
    summarize,
    write_html,
    write_json,
    write_multi_target,
)
from phlatline.sdk import SDK_VERSION
from phlatline.sdk.models import CompletedRun
from phlatline.sdk.registry import (
    get_alert_channels,
    get_result_sinks,
)

# Importing phlatline.report registers LocalReportSink via its __init__
import phlatline.report  # noqa: F401


# --------------------------------------------------------------------------- #
# Banner & EE discovery
# --------------------------------------------------------------------------- #

_BANNER_TEMPLATE = r"""
  ╱╲          ╱╲          ╱╲
 ╱  ╲        ╱  ╲        ╱  ╲
╱    ╲______╱    ╲______╱    ╲_____
  phlatline · api diagnostic v{version}  (sdk v{sdk})
"""

_EE_MODULE_NAME = "phlatline_ee"


def _print_banner() -> None:
    """Render the ASCII art banner with the current OSS and SDK version strings."""
    click.echo(_BANNER_TEMPLATE.format(version=__version__, sdk=SDK_VERSION))


def _try_load_ee() -> list[str]:
    """Import phlatline_ee if installed; return the list of loaded modules."""
    try:
        ee = importlib.import_module(_EE_MODULE_NAME)
    except ImportError:
        return []
    return list(getattr(ee, "__loaded_modules__", []))


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #

class AuthConfigFile(BaseModel):
    """Wrapper model for YAML/JSON auth config files."""

    auth: dict[str, Any] | None = None


_CONFIG_YAML_SUFFIXES = frozenset({".yaml", ".yml"})


def _load_auth_config(path: str | None) -> dict[str, Any] | None:
    """Parse an auth config file and return the inner ``auth`` mapping.

    Supports both YAML (``.yaml``/``.yml``) and JSON formats.  The file is
    expected to have a top-level ``auth:`` key; the value of that key is what
    gets returned and forwarded to the auth-strategy layer.

    Args:
        path: Filesystem path to the config file, or ``None`` to skip auth.

    Returns:
        The parsed ``auth`` dict, or ``None`` if no path was given.

    Raises:
        click.ClickException: If the file does not exist.
    """
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        raise click.ClickException(f"Config file not found: {path}")
    text = p.read_text(encoding="utf-8")
    raw = yaml.safe_load(text) if p.suffix in _CONFIG_YAML_SUFFIXES else json.loads(text)
    parsed = AuthConfigFile.model_validate(raw or {})
    return parsed.auth


def _format_summary_line(summary: dict[str, int]) -> str:
    """Format a summary dict as a single human-readable result line.

    Args:
        summary: Mapping with keys ``total``, ``pass``, ``fail``, ``error``,
            and ``skip``.

    Returns:
        A fixed-width string suitable for display between divider lines.
    """
    return (
        f"  TOTAL: {summary['total']}   "
        f"PASS: {summary['pass']}   "
        f"FAIL: {summary['fail']}   "
        f"ERROR: {summary['error']}   "
        f"SKIP: {summary['skip']}"
    )


_SUMMARY_DIVIDER = "─" * 56


def _run_to_completed(run: TargetRun, project_name: str) -> CompletedRun:
    """Convert a raw ``TargetRun`` into the SDK ``CompletedRun`` wire format.

    The conversion reconstructs ``started_at`` from the run's duration so
    that sinks always receive an absolute timestamp regardless of when the
    run object was created.

    Args:
        run: The finished target run produced by ``run_target()``.
        project_name: The logical project name to embed in the payload.

    Returns:
        A ``CompletedRun`` ready for fan-out to registered ``ResultSink``s.
    """
    summary = summarize(run.results)
    return CompletedRun(
        project_name=project_name,
        target_name=run.target.name,
        base_url=run.base_url,
        started_at=time.time() - run.duration_s,
        duration_s=run.duration_s,
        summary=summary,
        results=run.results,
        meta={
            "fuzz_warning": run.fuzz_warning,
            "run_error": run.error,
            "schema": run.target.schema_source,
        },
    )


def _emit_to_sinks(completed: CompletedRun) -> None:
    """Fan a completed run out to every registered ``ResultSink``.

    Errors from individual sinks are printed to stderr but never re-raised,
    so a misbehaving sink cannot abort the CLI process.

    Args:
        completed: The finished run payload to deliver.
    """
    for sink in get_result_sinks():
        try:
            sink.emit(completed)
        except Exception as e:
            click.echo(f"[phlatline] sink {sink.name!r} failed: "
                       f"{type(e).__name__}: {e}", err=True)


_DEFAULT_DRAIN_TIMEOUT_S = 10.0


def _drain_all() -> None:
    """Flush all registered sinks and alert channels before process exit.

    Each component's ``drain()`` is called with the default timeout.  Errors
    are logged to stderr so that the CLI can still exit cleanly even if a
    remote sync fails.
    """
    timeout = _DEFAULT_DRAIN_TIMEOUT_S
    for sink in get_result_sinks():
        try:
            sink.drain(timeout)
        except Exception as e:
            click.echo(f"[phlatline] drain({sink.name!r}) failed: "
                       f"{type(e).__name__}: {e}", err=True)
    for ch in get_alert_channels():
        try:
            ch.drain(timeout)
        except Exception as e:
            click.echo(f"[phlatline] drain({ch.name!r}) failed: "
                       f"{type(e).__name__}: {e}", err=True)


def _report_dir_override(output_dir: str | None) -> Path:
    """Apply an optional output-directory override and return the active path.

    When ``output_dir`` is provided, the global ``settings.report.output_dir``
    is updated in-place so that all downstream report writers use the same
    location without needing to receive the path explicitly.

    Args:
        output_dir: CLI-supplied directory string, or ``None`` to keep default.

    Returns:
        The resolved output directory as a ``Path``.
    """
    if output_dir:
        settings.report.output_dir = Path(output_dir)
    return settings.report.output_dir


# --------------------------------------------------------------------------- #
# Click CLI
# --------------------------------------------------------------------------- #

@click.group(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, "-V", "--version", prog_name="phlatline")
@click.option("--no-banner", is_flag=True, help="Suppress the CLI banner.")
@click.pass_context
def cli(ctx: click.Context, no_banner: bool) -> None:
    """Phlatline — No spikes. No surprises.

    \b
    Use `phlatline scan SCHEMA` to run against a single schema.
    Use `phlatline project FILE` for multi-target runs.
    """
    ctx.ensure_object(dict)
    ctx.obj["no_banner"] = no_banner

    if not no_banner:
        _print_banner()

    loaded = _try_load_ee()
    if loaded:
        click.echo(f"▸ phlatline-ee modules loaded: {', '.join(loaded)}")

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(0)


@cli.command()
@click.argument("schema", required=True)
@click.option("--base-url", help="Override the base URL from the schema.")
@click.option("--config", "config_path",
              type=click.Path(exists=True, dir_okay=False),
              help="Path to auth config (JSON/YAML).")
@click.option("--output-dir", help="Where to write reports.")
@click.option("--no-fuzz", is_flag=True, help="Skip the fuzzing stage.")
@click.option("--fuzz-examples", type=int,
              help="Fuzz examples per operation.")
@click.option("--no-verify-ssl", is_flag=True, help="Skip TLS verification.")
@click.pass_context
def scan(ctx: click.Context, schema: str, base_url: str | None,
         config_path: str | None, output_dir: str | None,
         no_fuzz: bool, fuzz_examples: int | None,
         no_verify_ssl: bool) -> None:
    """Run the test suite against a single SCHEMA (file path or URL)."""
    _report_dir_override(output_dir)

    if fuzz_examples is not None:
        settings.fuzz.examples_per_operation = fuzz_examples
    if no_verify_ssl:
        settings.execution.verify_ssl = False

    try:
        auth = _load_auth_config(config_path)
    except click.ClickException:
        raise

    target = ProjectTargetConfig(
        name="phlatline-run",
        schema=schema,
        base_url=base_url,
        auth=auth,
        fuzz=not no_fuzz,
    )

    click.echo(f"▸ Loading schema: {target.schema_source}")
    run = run_target(target)
    if run.error:
        click.echo(f"[!] {run.error}", err=True)
        ctx.exit(2)

    click.echo(f"▸ Base URL: {run.base_url}")
    click.echo(f"▸ Auth: {(target.auth or {}).get('type') or 'none'}")
    click.echo(f"▸ {len(run.results)} cases executed in {run.duration_s:.2f}s")
    if run.fuzz_warning:
        click.echo(f"[!] {run.fuzz_warning}", err=True)

    # Fan out through the SDK so cloud/alert extensions see the run
    completed = _run_to_completed(run, project_name=target.name)
    _emit_to_sinks(completed)

    # Upload to Phlatline Cloud if a token is configured
    from phlatline.cloud import upload_run as _cloud_upload
    try:
        run_url = _cloud_upload(completed)
        if run_url:
            click.echo(f"▸ Cloud run: {run_url}")
    except Exception as e:  # noqa: BLE001
        click.echo(f"[!] Cloud upload failed: {e}", err=True)

    # The local sink already wrote files via emit; report the summary
    summary = summarize(run.results)
    summary_dict = {
        "total": summary.total, "pass": summary.pass_count,
        "fail": summary.fail, "error": summary.error, "skip": summary.skip,
    }
    click.echo("")
    click.echo(_SUMMARY_DIVIDER)
    click.echo(_format_summary_line(summary_dict))
    click.echo(_SUMMARY_DIVIDER)
    for sink in get_result_sinks():
        click.echo(f"▸ Emitted to sink: {sink.name}")

    _drain_all()

    failed = summary.fail > 0 or summary.error > 0
    ctx.exit(1 if failed else 0)


@cli.command()
@click.argument("project_file", type=click.Path(exists=True, dir_okay=False), required=True)
@click.option("--output-dir", help="Where to write reports.")
@click.option("--parallel", "parallel_flag", is_flag=True,
              help="Run targets in parallel (requires phlatline-ee).")
@click.option("--sequential", is_flag=True, help="Run targets sequentially.")
@click.option("--max-parallel", type=int, help="Max concurrent targets when --parallel.")
@click.pass_context
def project(ctx: click.Context, project_file: str, output_dir: str | None,
            parallel_flag: bool, sequential: bool,
            max_parallel: int | None) -> None:
    """Run a multi-target PROJECT_FILE."""
    _report_dir_override(output_dir)

    try:
        spec = load_project(project_file)
    except ProjectLoadError as e:
        click.echo(f"[!] {e}", err=True)
        ctx.exit(2)
        return

    if parallel_flag and sequential:
        click.echo("[!] --parallel and --sequential are mutually exclusive", err=True)
        ctx.exit(2)
    if parallel_flag:
        spec.parallel = True
    if sequential:
        spec.parallel = False
    if max_parallel is not None:
        spec.max_parallel_targets = max_parallel

    click.echo(f"▸ Project: {spec.name}")
    mode = f"parallel, max {spec.max_parallel_targets}" if spec.parallel else "sequential"
    click.echo(f"▸ Targets: {len(spec.targets)} ({mode})")
    click.echo("")

    started = time.perf_counter()

    # Parallel orchestration is an EE-provided capability. If requested but
    # EE isn't available, fall back to sequential with a warning.
    if spec.parallel:
        runs = _maybe_run_parallel(spec)
    else:
        runs = [_run_one_verbose(t) for t in spec.targets]

    total_duration = time.perf_counter() - started

    paths = write_multi_target(spec, runs, total_duration)

    combined = summarize([r for run in runs for r in run.results])
    combined_dict = {
        "total": combined.total, "pass": combined.pass_count,
        "fail": combined.fail, "error": combined.error, "skip": combined.skip,
    }

    click.echo("")
    click.echo(_SUMMARY_DIVIDER)
    click.echo(f"  PROJECT: {spec.name}   ({total_duration:.2f}s total)")
    click.echo(_format_summary_line(combined_dict))
    click.echo(_SUMMARY_DIVIDER)
    click.echo(f"▸ Index:           {paths.index}")
    click.echo(f"▸ Combined report: {paths.combined_html}")
    click.echo(f"▸ Combined JSON:   {paths.combined_json}")
    click.echo(f"▸ Per-target:      {paths.per_target_dir}/<target>/report.html")

    _drain_all()

    failed = combined.fail > 0 or combined.error > 0 or any(r.error for r in runs)
    ctx.exit(1 if failed else 0)


def _run_one_verbose(target: ProjectTargetConfig) -> TargetRun:
    click.echo(f"▸ [{target.name}] starting…")
    run = run_target(target)
    _log_target_result(run)
    return run


def _log_target_result(run: TargetRun) -> None:
    if run.error:
        click.echo(f"▸ [{run.target.name}] errored: {run.error}")
        return
    s = summarize(run.results)
    verdict = "phlatlined" if s.fail == 0 and s.error == 0 else "spiking"
    click.echo(f"▸ [{run.target.name}] {verdict} — "
               f"{s.pass_count}/{s.total} pass, {s.fail} fail, {s.error} err "
               f"({run.duration_s:.2f}s)")


def _maybe_run_parallel(spec) -> list[TargetRun]:
    """Dispatch to the registered executor (EE plugin if installed, else default).

    Per ADR-004, the OSS package does not reference EE or Cloud packages
    directly. If phlatline-ee is installed, its module-level code registers
    a parallel executor at import time; we pick it up here via the SDK
    registry. If EE is absent, the default sequential executor runs.
    """
    try:
        import phlatline_ee  # noqa: F401  triggers EE's self-registration
    except ImportError:
        pass

    from phlatline.sdk.registry import get_executor
    executor = get_executor()

    if executor.name == "sequential" and spec.max_parallel_targets > 1:
        click.echo("[!] --parallel requested but no parallel executor is registered; "
                   "install phlatline-ee for concurrent execution. Falling back to sequential.",
                   err=True)
        return [_run_one_verbose(t) for t in spec.targets]

    # Delegate to whichever executor is registered
    return executor.run_targets(  # type: ignore[attr-defined]
        spec.targets,
        max_parallel=spec.max_parallel_targets,
        on_target_start=lambda t: click.echo(f"▸ [{t.name}] starting…"),
        on_target_done=_log_target_result,
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    """Entry point that supports legacy `phlatline SCHEMA` invocation.

    If the first positional arg is not a known subcommand, rewrite the
    argv to insert `scan` so `phlatline http://…/openapi.json` still works.
    """
    argv = argv if argv is not None else sys.argv[1:]
    known_commands = {"scan", "project"}

    # If there's a non-flag first arg and it's not a known command, inject 'scan'
    first_non_flag = next((a for a in argv if not a.startswith("-")), None)
    if first_non_flag and first_non_flag not in known_commands:
        argv = ["scan"] + argv

    try:
        cli.main(args=argv, standalone_mode=False)
    except click.exceptions.Exit as e:
        return e.exit_code
    except click.ClickException as e:
        e.show()
        return e.exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main())
