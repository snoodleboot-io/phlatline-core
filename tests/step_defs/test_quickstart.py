"""Step definitions for tests/features/quickstart.feature."""
from __future__ import annotations

import re
from pathlib import Path

from click.testing import CliRunner
from pytest_bdd import given, scenarios, then, when

scenarios("../features/quickstart.feature")

_PACKAGE_ROOT = Path(__file__).parent.parent.parent
_INSTALL_MD = _PACKAGE_ROOT / "INSTALL.md"
_FIXTURE_SPEC = _PACKAGE_ROOT / "tests" / "fixtures" / "specs" / "openapi_3_0.yaml"


# ─── Scenario 1: quickstart scan ────────────────────────────────────────────

@given("phlatline-core is installed and a local spec is available", target_fixture="spec_path")
def _installed() -> Path:
    assert _FIXTURE_SPEC.exists(), f"Fixture spec not found: {_FIXTURE_SPEC}"
    return _FIXTURE_SPEC


@when("the user runs the quickstart scan", target_fixture="scan_context")
def _run_quickstart(
    spec_path: Path,
    cli_runner: CliRunner,
    monkeypatch: object,
    tmp_path: Path,
) -> dict:
    from phlatline.cli import cli
    from phlatline.core.project import ProjectTargetConfig
    from phlatline.core.runner import TargetRun
    from phlatline.report.local_sink import LocalReportSink

    target = ProjectTargetConfig(name="phlatline-run", schema=str(spec_path))
    fake_run = TargetRun(
        target=target,
        base_url="http://localhost",
        results=[],
        duration_s=0.05,
        error=None,
    )

    monkeypatch.setattr("phlatline.cli.run_target", lambda *a, **kw: fake_run)

    # Redirect sinks to tmp_path so the HTML lands in a predictable, isolated location.
    local_sink = LocalReportSink(output_dir=tmp_path)
    monkeypatch.setattr("phlatline.cli.get_result_sinks", lambda: [local_sink])
    monkeypatch.setattr("phlatline.cli.get_alert_channels", lambda: [])

    result = cli_runner.invoke(cli, ["--no-banner", "scan", str(spec_path)])
    return {"result": result, "outdir": tmp_path}


@then("the command exits with code 0")
def _exits_ok(scan_context: dict) -> None:
    assert scan_context["result"].exit_code == 0, (
        f"exit_code={scan_context['result'].exit_code}\n"
        f"output:\n{scan_context['result'].output}"
    )


@then("an HTML report file is created in the output directory")
def _html_created(scan_context: dict) -> None:
    html_files = list(Path(scan_context["outdir"]).glob("**/*.html"))
    assert html_files, (
        f"No HTML files found under {scan_context['outdir']}\n"
        f"CLI output:\n{scan_context['result'].output}"
    )


# ─── Scenario 2: INSTALL.md coverage ────────────────────────────────────────

@given("INSTALL.md exists in the package root", target_fixture="install_md_text")
def _install_md_exists() -> str:
    assert _INSTALL_MD.exists(), f"INSTALL.md not found at {_INSTALL_MD}"
    return _INSTALL_MD.read_text(encoding="utf-8")


@when("I inspect its contents")
def _inspect(install_md_text: str) -> None:
    pass  # content already loaded by the Given step


def _has_section(text: str, *keywords: str) -> bool:
    pattern = r"^#{1,4}\s+.*(?:" + "|".join(re.escape(k) for k in keywords) + r").*$"
    return bool(re.search(pattern, text, re.IGNORECASE | re.MULTILINE))


def _section_has_command(text: str, *section_keywords: str) -> bool:
    """Return True if the section whose heading contains a keyword has a shell command."""
    in_section = False
    for line in text.splitlines():
        if re.match(r"^#{1,4}\s+", line):
            in_section = any(k.lower() in line.lower() for k in section_keywords)
        if in_section and re.search(r"(^\$\s|phlatline |pip )", line):
            return True
    return False


@then("it includes a section for network errors")
def _section_network(install_md_text: str) -> None:
    assert _has_section(install_md_text, "network", "connection"), \
        "INSTALL.md is missing a section for network errors"


@then("it includes a section for schema 404s")
def _section_404(install_md_text: str) -> None:
    assert _has_section(install_md_text, "404", "not found", "schema not found"), \
        "INSTALL.md is missing a section for schema 404s"


@then("it includes a section for auth failures")
def _section_auth(install_md_text: str) -> None:
    assert _has_section(install_md_text, "auth"), \
        "INSTALL.md is missing a section for auth failures"


@then("it includes a section for unsupported Python versions")
def _section_python(install_md_text: str) -> None:
    assert _has_section(install_md_text, "python", "version"), \
        "INSTALL.md is missing a section for unsupported Python versions"


@then("each section has a reproducible command and expected error")
def _commands_present(install_md_text: str) -> None:
    sections: list[tuple[str, ...]] = [
        ("network", "connection"),
        ("404", "not found"),
        ("auth",),
        ("python", "version"),
    ]
    for keywords in sections:
        assert _section_has_command(install_md_text, *keywords), (
            f"INSTALL.md section matching {keywords!r} has no reproducible command"
        )
