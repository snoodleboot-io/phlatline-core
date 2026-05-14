"""Step definitions for tests/features/schema_loader.feature."""
from __future__ import annotations

from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from phlatline.core.schema_loader import (
    SchemaLoadError,
    load_schema,
    resolve_base_url,
)

scenarios("../features/schema_loader.feature")


@given(parsers.parse('a fixture spec at "{path}"'), target_fixture="spec_path")
def _spec_path(path: str) -> str:
    return path


@given(parsers.parse('a non-existent file "{path}"'), target_fixture="spec_path")
def _bad_path(path: str) -> str:
    return path


@when("the schema is loaded", target_fixture="load_result")
def _load(spec_path: str) -> Any:
    try:
        return load_schema(spec_path)
    except SchemaLoadError as e:
        return e


@then(parsers.parse('the schema contains a "{key}" key with value "{value}"'))
def _has_key_value(load_result: Any, key: str, value: str) -> None:
    assert isinstance(load_result, dict)
    assert load_result.get(key) == value


@then(parsers.parse('the schema contains an "{key}" key starting with "{prefix}"'))
def _key_starts_with(load_result: Any, key: str, prefix: str) -> None:
    assert isinstance(load_result, dict)
    assert str(load_result.get(key, "")).startswith(prefix)


@then("the schema contains at least one path")
def _has_paths(load_result: Any) -> None:
    assert isinstance(load_result, dict)
    assert len(load_result.get("paths", {})) >= 1


@then("a SchemaLoadError is raised")
def _raises(load_result: Any) -> None:
    assert isinstance(load_result, SchemaLoadError)


@given(parsers.parse('an OpenAPI 3.0 schema with a server "{url}"'), target_fixture="schema")
def _schema_with_server(url: str) -> dict[str, Any]:
    return {"openapi": "3.0.0", "servers": [{"url": url}]}


@when("resolve_base_url is called without an override", target_fixture="resolved")
def _resolve_no_override(schema: dict[str, Any]) -> str:
    return resolve_base_url(schema, None)


@when(parsers.parse('resolve_base_url is called with override "{url}"'), target_fixture="resolved")
def _resolve_with_override(schema: dict[str, Any], url: str) -> str:
    return resolve_base_url(schema, url)


@then(parsers.parse('the resolved URL is "{expected}"'))
def _resolved_url_matches(resolved: str, expected: str) -> None:
    assert resolved == expected
