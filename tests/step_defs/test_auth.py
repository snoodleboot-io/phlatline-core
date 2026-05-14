"""Step definitions for tests/features/auth.feature."""
from __future__ import annotations

from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

from phlatline.core.auth import AuthContext, build_auth_context

scenarios("../features/auth.feature")


@given(parsers.parse('a bearer auth context with token "{token}"'), target_fixture="cfg")
def _bearer_cfg(token: str) -> dict[str, Any]:
    return {"type": "bearer", "token": token}


@given(parsers.parse('a basic auth context with username "{user}" and password "{pwd}"'), target_fixture="cfg")
def _basic_cfg(user: str, pwd: str) -> dict[str, Any]:
    return {"type": "basic", "username": user, "password": pwd}


@given(parsers.parse('an api-key auth context with key "{key}" in header "{name}"'), target_fixture="cfg")
def _api_key_header(key: str, name: str) -> dict[str, Any]:
    return {"type": "api_key", "value": key, "name": name, "in": "header"}


@given(parsers.parse('an api-key auth context with key "{key}" in query "{name}"'), target_fixture="cfg")
def _api_key_query(key: str, name: str) -> dict[str, Any]:
    return {"type": "api_key", "value": key, "name": name, "in": "query"}


@given("no auth configuration", target_fixture="cfg")
def _no_cfg() -> None:
    return None


@when("the strategy is applied to an empty request", target_fixture="ctx")
def _apply(cfg: dict[str, Any] | None) -> AuthContext:
    return build_auth_context(cfg)


@then(parsers.parse('the headers include "{name}: {value}"'))
def _header_exact(ctx: AuthContext, name: str, value: str) -> None:
    assert ctx.headers.get(name) == value, f"headers: {ctx.headers}"


@then(parsers.parse('the headers include an "{name}" header starting with "{prefix}"'))
def _header_starts(ctx: AuthContext, name: str, prefix: str) -> None:
    assert name in ctx.headers, f"{name} not in {list(ctx.headers)}"
    assert ctx.headers[name].startswith(prefix), f"{ctx.headers[name]!r}"


@then(parsers.parse('the query params include "{name}={value}"'))
def _query_has(ctx: AuthContext, name: str, value: str) -> None:
    assert ctx.query_params.get(name) == value


@then("the request is unchanged")
def _unchanged(ctx: AuthContext) -> None:
    assert ctx.headers == {}
    assert ctx.query_params == {}
    assert ctx.cookies == {}
