"""Step definitions for tests/features/packaging.feature."""
from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pytest_bdd import given, parsers, scenarios, then, when

from phlatline.core.fuzzer import FuzzResult, run_fuzzing

scenarios("../features/packaging.feature")

_PACKAGE_ROOT = Path(__file__).parent.parent.parent
_PYPROJECT = _PACKAGE_ROOT / "pyproject.toml"


# ─── Scenario 1: the extra is declared ──────────────────────────────────────

@given("pyproject.toml exists in the package root", target_fixture="pyproject")
def _pyproject_exists() -> dict[str, Any]:
    assert _PYPROJECT.exists(), f"pyproject.toml not found at {_PYPROJECT}"
    return tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))


@when("I inspect its optional dependencies", target_fixture="optional_deps")
def _optional_deps(pyproject: dict[str, Any]) -> dict[str, list[str]]:
    return pyproject["project"].get("optional-dependencies", {})


@then(parsers.parse('a "{name}" extra is declared'))
def _extra_declared(optional_deps: dict[str, list[str]], name: str) -> None:
    assert name in optional_deps, (
        f"'{name}' extra not declared — got {sorted(optional_deps)}"
    )


@then(parsers.parse('the "{name}" extra requires "{package}"'))
def _extra_requires(optional_deps: dict[str, list[str]], name: str, package: str) -> None:
    requirements = optional_deps.get(name, [])
    assert any(req.split()[0].split(">")[0].split("=")[0].strip() == package
               for req in requirements), \
        f"'{package}' not required by the '{name}' extra — got {requirements}"


# ─── Scenario 2: the skip message names the extra ───────────────────────────

@given("Schemathesis is not installed")
def _schemathesis_absent() -> None:
    pass  # enforced in the When step, so the patch wraps the call itself


@when("fuzzing runs against a schema", target_fixture="fuzz_result")
def _run_fuzzing_without_schemathesis() -> FuzzResult:
    # Mapping the name to None in sys.modules makes `import schemathesis`
    # raise ImportError even when the package is installed, so the scenario
    # behaves identically with and without the fuzz extra present.
    with patch.dict(sys.modules, {"schemathesis": None}):
        return run_fuzzing("openapi.yaml", "https://api.example.com", None)


@then("no fuzz results are produced")
def _no_results(fuzz_result: FuzzResult) -> None:
    assert fuzz_result.results == [], \
        f"expected no results, got {len(fuzz_result.results)}"


@then(parsers.parse('the warning tells the user to install "{target}"'))
def _warning_names_extra(fuzz_result: FuzzResult, target: str) -> None:
    assert fuzz_result.warning is not None, "expected a skip warning, got none"
    assert target in fuzz_result.warning, \
        f"'{target}' not mentioned in skip warning: {fuzz_result.warning!r}"
