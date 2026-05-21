"""Step definitions for tests/features/docs_site.feature."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from pytest_bdd import given, parsers, scenarios, then, when

scenarios("../features/docs_site.feature")

_PACKAGE_ROOT = Path(__file__).parent.parent.parent
_MKDOCS_YML = _PACKAGE_ROOT / "mkdocs.yml"
_GEN_SCRIPT = _PACKAGE_ROOT / "scripts" / "gen_cli_reference.py"

# Scenarios 1 & 2 require mkdocs to be installed.
_MKDOCS_BIN = shutil.which("mkdocs")
_mkdocs_required = pytest.mark.skipif(
    _MKDOCS_BIN is None,
    reason="mkdocs not installed — run: pip install 'phlatline-core[docs]'",
)


# ─── Scenario 1: build produces nav links ───────────────────────────────────

@_mkdocs_required
@given("mkdocs is installed with the Material theme", target_fixture="mkdocs_bin")
def _mkdocs_installed() -> str:
    assert _MKDOCS_BIN is not None
    return _MKDOCS_BIN


@_mkdocs_required
@when('"mkdocs build --strict" runs in the package directory', target_fixture="built_site")
def _build_site(mkdocs_bin: str, tmp_path: Path) -> Path:
    result = subprocess.run(
        [mkdocs_bin, "build", "--strict", "--site-dir", str(tmp_path)],
        cwd=str(_PACKAGE_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"mkdocs build failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return tmp_path


@_mkdocs_required
@then("site/index.html is created")
def _index_exists(built_site: Path) -> None:
    assert (built_site / "index.html").exists(), \
        f"index.html not found under {built_site}"


@_mkdocs_required
@then(parsers.parse('it contains a link labelled "{label}"'))
def _has_nav_link(built_site: Path, label: str) -> None:
    html = (built_site / "index.html").read_text(encoding="utf-8")
    assert label in html, f"'{label}' not found in site/index.html"


# ─── Scenario 2: search index ───────────────────────────────────────────────

@_mkdocs_required
@given("the docs site has been built", target_fixture="built_site")
def _site_built(tmp_path: Path) -> Path:
    assert _MKDOCS_BIN is not None
    result = subprocess.run(
        [_MKDOCS_BIN, "build", "--site-dir", str(tmp_path)],
        cwd=str(_PACKAGE_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return tmp_path


@_mkdocs_required
@when("I inspect the search index", target_fixture="search_index")
def _load_search_index(built_site: Path) -> dict[str, Any]:
    index_path = built_site / "search" / "search_index.json"
    assert index_path.exists(), f"search_index.json not found under {built_site}"
    return json.loads(index_path.read_text(encoding="utf-8"))


@_mkdocs_required
@then(parsers.parse('it contains an entry mentioning "{term}"'))
def _search_contains(search_index: dict[str, Any], term: str) -> None:
    docs = search_index.get("docs", [])
    matched = any(
        term.lower() in (d.get("text") or "").lower()
        or term.lower() in (d.get("title") or "").lower()
        for d in docs
    )
    assert matched, f"'{term}' not found in search index"


# ─── Scenario 3: CLI reference gen ──────────────────────────────────────────

@given("the phlatline-core package is installed", target_fixture="phlatline_exe")
def _phlatline_installed() -> str:
    exe = shutil.which("phlatline")
    assert exe is not None, "phlatline not found — run: pip install -e ."
    return exe


@when("the CLI reference generator script runs", target_fixture="gen_output_path")
def _run_gen(phlatline_exe: str, tmp_path: Path) -> Path:
    assert _GEN_SCRIPT.exists(), f"Generator script not found: {_GEN_SCRIPT}"
    out = tmp_path / "cli-reference.md"
    result = subprocess.run(
        [sys.executable, str(_GEN_SCRIPT), "--output", str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Generator failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return out


@then("a Markdown file is produced")
def _md_exists(gen_output_path: Path) -> None:
    assert gen_output_path.exists(), f"No output file at {gen_output_path}"
    assert gen_output_path.stat().st_size > 0, "Output file is empty"


@then(parsers.parse('it contains documentation for the "{cmd}" command'))
def _has_cmd_docs(gen_output_path: Path, cmd: str) -> None:
    text = gen_output_path.read_text(encoding="utf-8")
    assert cmd in text, f"'{cmd}' command not found in generated CLI reference"


@then(parsers.parse('it contains the "{option}" option'))
def _has_option(gen_output_path: Path, option: str) -> None:
    text = gen_output_path.read_text(encoding="utf-8")
    assert option in text, f"Option '{option}' not found in generated CLI reference"


# ─── Scenario 4: mobile / responsive configuration ──────────────────────────

@given("mkdocs.yml exists in the package root", target_fixture="mkdocs_config")
def _mkdocs_yml_exists() -> dict[str, Any]:
    assert _MKDOCS_YML.exists(), f"mkdocs.yml not found at {_MKDOCS_YML}"
    return yaml.safe_load(_MKDOCS_YML.read_text(encoding="utf-8"))


@when("I inspect its configuration")
def _inspect_config(mkdocs_config: dict[str, Any]) -> None:
    pass  # config already loaded by the Given step


@then("the Material theme is declared")
def _material_declared(mkdocs_config: dict[str, Any]) -> None:
    theme = mkdocs_config.get("theme", {})
    assert theme.get("name") == "material", \
        f"Expected theme.name='material', got {theme.get('name')!r}"


@then("responsive navigation features are enabled")
def _responsive_features(mkdocs_config: dict[str, Any]) -> None:
    features = mkdocs_config.get("theme", {}).get("features", [])
    responsive_features = {
        "navigation.top",
        "navigation.tabs",
    }
    found = responsive_features & set(features)
    assert found, (
        f"No responsive nav features found in theme.features. "
        f"Expected at least one of {responsive_features}, got {features}"
    )
