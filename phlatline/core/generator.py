"""Test case generation — Strategy pattern over test categories.

Each CaseGenerator produces cases for one category. The top-level
generate_test_cases() delegates to all registered generators.

Adding a new test category = adding a new CaseGenerator subclass and
registering it in the generator list. Core never changes.
"""
from __future__ import annotations

import random
import secrets
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from phlatline.config.enums import HttpMethod, TestCategory
from phlatline.config.settings import settings
from phlatline.core.schema_utils import example_for, resolve_ref, substitute_path
from phlatline.sdk.models import TestCase


# --------------------------------------------------------------------------- #
# Shared parameter resolution
# --------------------------------------------------------------------------- #

# Header parameter names that collide with our AuthContext.
# When a spec declares these as header params, we don't fill them with dummy
# examples — the real AuthContext takes that slot.
_AUTH_HEADER_NAMES: frozenset[str] = frozenset({
    "authorization", "cookie",
    "x-api-key", "api-key", "apikey",
    "x-auth-token", "x-access-token", "x-token",
})

_PARAM_LOCATION_PATH = "path"
_PARAM_LOCATION_QUERY = "query"
_PARAM_LOCATION_HEADER = "header"

# Request shapes & response codes
_JSON_MEDIA_TYPE = "application/json"
_STATUS_FAMILY_2XX = (2,)
_STATUS_FAMILY_3XX = (3,)
_STATUS_FAMILY_4XX = (4,)
_STATUS_FAMILY_2XX_OR_4XX = (2, 4)


class _ResolvedParams:
    """Lightweight container for the three param-destination buckets."""

    __slots__ = ("path_vals", "query_vals", "headers")

    def __init__(self) -> None:
        self.path_vals: dict[str, Any] = {}
        self.query_vals: dict[str, Any] = {}
        self.headers: dict[str, str] = {}


def _resolve_parameters(
    params: list[dict[str, Any]],
    schema: dict[str, Any],
) -> _ResolvedParams:
    """Fill path/query/header buckets with example values from the schema."""
    out = _ResolvedParams()
    optional_prob = settings.generation.optional_query_param_probability

    for p in params:
        name = p.get("name")
        if not name:
            continue
        location = p.get("in")
        pschema = resolve_ref(p.get("schema") or {}, schema)
        example = p.get("example")
        if example is None:
            example = pschema.get("example")
        if example is None:
            example = example_for(pschema, root=schema)

        match location:
            case s if s == _PARAM_LOCATION_PATH:
                out.path_vals[name] = example
            case s if s == _PARAM_LOCATION_QUERY:
                if p.get("required") or random.random() < optional_prob:
                    out.query_vals[name] = example
            case s if s == _PARAM_LOCATION_HEADER:
                if name.lower() not in _AUTH_HEADER_NAMES:
                    out.headers[name] = str(example)
    return out


def _build_request_body(op: dict[str, Any], schema: dict[str, Any]) -> Any:
    """Build an example request body from the operation's requestBody spec."""
    rb = op.get("requestBody")
    if not rb:
        return None

    content = rb.get("content") or {}
    media = content.get(_JSON_MEDIA_TYPE) or next(iter(content.values()), None)
    if not isinstance(media, dict):
        return None

    if "example" in media:
        return media["example"]

    examples = media.get("examples")
    if isinstance(examples, dict):
        first = next(iter(examples.values()), None)
        if isinstance(first, dict) and "value" in first:
            return first["value"]

    body_schema = resolve_ref(media.get("schema") or {}, schema)
    return example_for(body_schema, root=schema)


def _documented_success_family(op: dict[str, Any]) -> tuple[int, ...]:
    responses = op.get("responses") or {}
    documented_codes = [str(c) for c in responses.keys()]
    has_2xx = any(c.startswith("2") or c == "default" for c in documented_codes)
    return _STATUS_FAMILY_2XX if has_2xx else _STATUS_FAMILY_2XX + _STATUS_FAMILY_3XX


# --------------------------------------------------------------------------- #
# Operation context — shared immutable view passed to each generator
# --------------------------------------------------------------------------- #

class _OpContext:
    """Immutable view of an OpenAPI operation ready to emit test cases for."""

    __slots__ = ("method", "path_template", "operation_id", "summary",
                 "op", "params", "schema", "resolved", "body")

    def __init__(
        self,
        method: HttpMethod,
        path_template: str,
        operation_id: str,
        summary: str,
        op: dict[str, Any],
        params: list[dict[str, Any]],
        schema: dict[str, Any],
    ) -> None:
        self.method = method
        self.path_template = path_template
        self.operation_id = operation_id
        self.summary = summary
        self.op = op
        self.params = params
        self.schema = schema
        self.resolved = _resolve_parameters(params, schema)
        self.body = _build_request_body(op, schema)


# --------------------------------------------------------------------------- #
# Strategy: CaseGenerator
# --------------------------------------------------------------------------- #

class CaseGenerator(ABC):
    """Generates TestCases for one category.

    Implementations are stateless; they read from the op context and yield
    new TestCase objects.
    """

    category: TestCategory

    @abstractmethod
    def generate(self, ctx: _OpContext) -> Iterable[TestCase]: ...


class HappyPathGenerator(CaseGenerator):
    category = TestCategory.HAPPY

    def generate(self, ctx: _OpContext) -> Iterable[TestCase]:
        yield TestCase(
            test_id=f"{ctx.operation_id}::happy",
            category=self.category,
            method=ctx.method,
            path=substitute_path(ctx.path_template, ctx.resolved.path_vals),
            path_template=ctx.path_template,
            operation_id=ctx.operation_id,
            summary=f"Happy path — {ctx.summary}",
            query_params=dict(ctx.resolved.query_vals),
            headers=dict(ctx.resolved.headers),
            body=ctx.body,
            send_auth=True,
            expected_status_family=_documented_success_family(ctx.op),
        )


class NegativeCaseGenerator(CaseGenerator):
    category = TestCategory.NEGATIVE

    _MALFORMED_BODY_PAYLOAD = "this-is-not-valid-json-for-the-schema"

    def generate(self, ctx: _OpContext) -> Iterable[TestCase]:
        has_body = bool(ctx.op.get("requestBody"))
        required_params = [p for p in ctx.params if p.get("required")]

        if not has_body and not required_params:
            return

        base_path = substitute_path(ctx.path_template, ctx.resolved.path_vals)

        if has_body:
            yield TestCase(
                test_id=f"{ctx.operation_id}::negative_bad_body",
                category=self.category,
                method=ctx.method,
                path=base_path,
                path_template=ctx.path_template,
                operation_id=ctx.operation_id,
                summary=f"Negative: malformed body — {ctx.summary}",
                query_params=dict(ctx.resolved.query_vals),
                headers=dict(ctx.resolved.headers),
                body=self._MALFORMED_BODY_PAYLOAD,
                send_auth=True,
                expected_status_family=_STATUS_FAMILY_4XX,
            )

        if required_params:
            dropped = required_params[0].get("name")
            if not dropped:
                return
            bad_query = {k: v for k, v in ctx.resolved.query_vals.items() if k != dropped}
            bad_path_vals = dict(ctx.resolved.path_vals)
            if dropped in bad_path_vals:
                bad_path_vals[dropped] = ""

            yield TestCase(
                test_id=f"{ctx.operation_id}::negative_missing_{dropped}",
                category=self.category,
                method=ctx.method,
                path=substitute_path(ctx.path_template, bad_path_vals),
                path_template=ctx.path_template,
                operation_id=ctx.operation_id,
                summary=f"Negative: missing required '{dropped}' — {ctx.summary}",
                query_params=bad_query,
                headers=dict(ctx.resolved.headers),
                body=ctx.body,
                send_auth=True,
                expected_status_family=_STATUS_FAMILY_4XX,
            )


class AuthCaseGenerator(CaseGenerator):
    category = TestCategory.AUTH

    def generate(self, ctx: _OpContext) -> Iterable[TestCase]:
        security = ctx.op.get("security")
        if security is None:
            security = ctx.schema.get("security")
        if not security:
            return  # no auth declared

        yield TestCase(
            test_id=f"{ctx.operation_id}::auth_missing",
            category=self.category,
            method=ctx.method,
            path=substitute_path(ctx.path_template, ctx.resolved.path_vals),
            path_template=ctx.path_template,
            operation_id=ctx.operation_id,
            summary=f"Auth: no credentials — {ctx.summary}",
            query_params=dict(ctx.resolved.query_vals),
            headers=dict(ctx.resolved.headers),
            body=ctx.body,
            send_auth=False,
            expected_status_family=_STATUS_FAMILY_4XX,
        )


class BoundaryCaseGenerator(CaseGenerator):
    category = TestCategory.BOUNDARY

    def generate(self, ctx: _OpContext) -> Iterable[TestCase]:
        cfg = settings.generation

        numeric = [p for p in ctx.params
                   if (p.get("schema") or {}).get("type") in ("integer", "number")]
        strings = [p for p in ctx.params
                   if (p.get("schema") or {}).get("type") == "string"]

        yield from self._numeric_cases(ctx, numeric[:cfg.max_boundary_numeric_params])
        yield from self._string_cases(ctx, strings[:cfg.max_boundary_string_params])

    def _numeric_cases(self, ctx: _OpContext, params: list[dict[str, Any]]
                       ) -> Iterable[TestCase]:
        cfg = settings.generation
        bounds: list[tuple[str, int]] = [
            ("max", cfg.boundary_numeric_max),
            ("min_negative", cfg.boundary_numeric_min),
        ]
        for p in params:
            name = p.get("name")
            location = p.get("in")
            if not name or location not in (_PARAM_LOCATION_QUERY, _PARAM_LOCATION_PATH):
                continue
            for label, value in bounds:
                yield self._build_boundary_case(ctx, name, location, value, label)

    def _string_cases(self, ctx: _OpContext, params: list[dict[str, Any]]
                      ) -> Iterable[TestCase]:
        long_str = "A" * settings.generation.boundary_long_string_length
        for p in params:
            name = p.get("name")
            location = p.get("in")
            if not name or location not in (_PARAM_LOCATION_QUERY, _PARAM_LOCATION_PATH):
                continue
            yield self._build_boundary_case(ctx, name, location, long_str, "long_string")

    @staticmethod
    def _build_boundary_case(
        ctx: _OpContext,
        name: str,
        location: str,
        value: Any,
        label: str,
    ) -> TestCase:
        query = dict(ctx.resolved.query_vals)
        path_vals = dict(ctx.resolved.path_vals)
        if location == _PARAM_LOCATION_QUERY:
            query[name] = value
        elif location == _PARAM_LOCATION_PATH:
            path_vals[name] = value

        return TestCase(
            test_id=f"{ctx.operation_id}::boundary_{name}_{label}",
            category=TestCategory.BOUNDARY,
            method=ctx.method,
            path=substitute_path(ctx.path_template, path_vals),
            path_template=ctx.path_template,
            operation_id=ctx.operation_id,
            summary=f"Boundary {label} on {name!r} — {ctx.summary}",
            query_params=query,
            headers=dict(ctx.resolved.headers),
            body=ctx.body,
            send_auth=True,
            expected_status_family=_STATUS_FAMILY_2XX_OR_4XX,
        )


# --------------------------------------------------------------------------- #
# Registry of generators (ordered)
# --------------------------------------------------------------------------- #

_DEFAULT_GENERATORS: list[CaseGenerator] = [
    HappyPathGenerator(),
    NegativeCaseGenerator(),
    AuthCaseGenerator(),
    BoundaryCaseGenerator(),
]


def generate_test_cases(
    schema: dict[str, Any],
    generators: list[CaseGenerator] | None = None,
) -> list[TestCase]:
    """Walk the schema and produce all test cases.

    Pass a custom generators list to customize which categories are produced
    (e.g. for tests). Defaults to the full OSS set.
    """
    active_generators = generators if generators is not None else _DEFAULT_GENERATORS
    paths = schema.get("paths") or {}
    cases: list[TestCase] = []

    for path_template, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        path_level_params = path_item.get("parameters") or []

        for method_str, op in path_item.items():
            if not isinstance(op, dict):
                continue
            try:
                method = HttpMethod(method_str.upper())
            except ValueError:
                continue  # not an HTTP method (e.g. "parameters", "summary")

            op_params = (op.get("parameters") or []) + path_level_params
            op_id = op.get("operationId") or _synthesize_op_id(method, path_template)
            summary = op.get("summary") or op_id

            ctx = _OpContext(
                method=method,
                path_template=path_template,
                operation_id=op_id,
                summary=summary,
                op=op,
                params=op_params,
                schema=schema,
            )

            for generator in active_generators:
                cases.extend(generator.generate(ctx))

    return cases


def _synthesize_op_id(method: HttpMethod, path_template: str) -> str:
    """Build a readable operation id when the spec doesn't provide one."""
    return f"{method.value.lower()}_{path_template}"
