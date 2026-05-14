"""Step definitions for tests/features/generator.feature."""
from __future__ import annotations

from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from phlatline.core.generator import (
    HappyPathGenerator,
    generate_test_cases,
)
from phlatline.core.schema_loader import load_schema
from phlatline.sdk.models import TestCase

scenarios("../features/generator.feature")


import pytest


@pytest.fixture
def generators() -> list | None:
    """Default: None → generator uses its internal default set. Individual
    scenarios override via Given steps."""
    return None


@given("the OpenAPI 3.0 fixture spec is loaded", target_fixture="schema")
def _loaded_schema() -> dict[str, Any]:
    return load_schema("tests/fixtures/specs/openapi_3_0.yaml")


@given("only the HappyPathGenerator is selected", target_fixture="generators")
def _happy_only() -> list:
    return [HappyPathGenerator()]


@when("generate_test_cases runs for the whole schema", target_fixture="cases")
def _run(schema: dict[str, Any], generators: list | None) -> list[TestCase]:
    return generate_test_cases(schema, generators=generators)


@then(parsers.parse('at least one case has category "{category}"'))
def _has_category(cases: list[TestCase], category: str) -> None:
    matching = [c for c in cases if str(c.category) == category]
    assert len(matching) >= 1, (
        f"no cases with category {category!r}; found: {[str(c.category) for c in cases]}"
    )


@then(parsers.parse('every case has category "{category}"'))
def _all_have_category(cases: list[TestCase], category: str) -> None:
    mismatched = [c for c in cases if str(c.category) != category]
    assert not mismatched, f"cases with wrong category: {[str(c.category) for c in mismatched]}"
