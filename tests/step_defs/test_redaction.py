"""Step definitions for tests/features/redaction.feature."""
from __future__ import annotations

import json

from pytest_bdd import given, parsers, scenarios, then, when

from phlatline.core.redaction import (
    is_credential_name,
    looks_like_secret_value,
    redact_body,
    redact_headers,
    redact_query_params,
    redact_response_preview,
)

scenarios("../features/redaction.feature")


# --- Headers ---

@given(parsers.parse('a request with Authorization "{value}"'), target_fixture="headers")
def _auth_header(value: str) -> dict[str, str]:
    return {"Authorization": value}


@given(parsers.parse('a request with Cookie "{value}"'), target_fixture="headers")
def _cookie_header(value: str) -> dict[str, str]:
    return {"Cookie": value}


@when("redact_headers processes it", target_fixture="redacted_headers")
def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    return redact_headers(headers)


@then(parsers.parse('the result for "{name}" starts with "{prefix}"'))
def _starts_with(redacted_headers: dict[str, str], name: str, prefix: str) -> None:
    assert redacted_headers[name].startswith(prefix), f"{redacted_headers[name]!r}"


@then(parsers.parse('the result for "{name}" ends with "{suffix}"'))
def _ends_with(redacted_headers: dict[str, str], name: str, suffix: str) -> None:
    assert redacted_headers[name].endswith(suffix), f"{redacted_headers[name]!r}"


@then(parsers.parse('the result for "{name}" contains a mask character'))
def _contains_mask(redacted_headers: dict[str, str], name: str) -> None:
    assert "…" in redacted_headers[name] or "*" in redacted_headers[name]


@then(parsers.parse('the result for "{name}" is exactly "{expected}"'))
def _exact_match(redacted_headers: dict[str, str], name: str, expected: str) -> None:
    assert redacted_headers[name] == expected


# --- Credential name detection ---

@when("I check header names for credential-ness", target_fixture="cred_results")
def _check_headers() -> dict[str, bool]:
    return {
        "x-api-key": is_credential_name("x-api-key"),
        "api_token": is_credential_name("api_token"),
        "x-auth-token": is_credential_name("x-auth-token"),
        "content-type": is_credential_name("content-type"),
    }


@then(parsers.parse('"{name}" is identified as a credential'))
def _is_credential(cred_results: dict[str, bool], name: str) -> None:
    assert cred_results[name] is True


@then(parsers.parse('"{name}" is not identified as a credential'))
def _not_credential(cred_results: dict[str, bool], name: str) -> None:
    assert cred_results[name] is False


# --- Query params ---

@given(parsers.parse('query params with "{a}" and "{b}"'), target_fixture="query_params")
def _query_params(a: str, b: str) -> dict[str, str]:
    def _p(pair: str) -> tuple[str, str]:
        k, v = pair.split("=", 1)
        return k, v
    return dict([_p(a), _p(b)])


@when("redact_query_params processes them", target_fixture="redacted_query")
def _redact_query(query_params: dict[str, str]) -> dict[str, str]:
    return redact_query_params(query_params)


@then(parsers.parse('the "{key}" value starts with "{prefix}"'))
def _query_starts_with(redacted_query: dict[str, str], key: str, prefix: str) -> None:
    assert str(redacted_query[key]).startswith(prefix), f"{redacted_query[key]!r}"


@then(parsers.parse('the "{key}" value is preserved as "{expected}"'))
def _value_preserved(redacted_query: dict[str, str], key: str, expected: str) -> None:
    assert str(redacted_query[key]) == expected


# --- Body ---

@given(parsers.parse('a body with {body_json}'), target_fixture="body")
def _body(body_json: str) -> dict:
    return json.loads(body_json)


@when("redact_body processes it", target_fixture="redacted_body")
def _redact_body(body: dict) -> dict:
    return redact_body(body)


@then(parsers.parse('the "{field}" field value starts with "{prefix}"'))
def _body_field_starts(redacted_body: dict, field: str, prefix: str) -> None:
    assert str(redacted_body[field]).startswith(prefix), f"{redacted_body[field]!r}"


@then(parsers.parse('the "{field}" field value is preserved'))
def _body_field_preserved(redacted_body: dict, body: dict, field: str) -> None:
    assert redacted_body[field] == body[field]


@then(parsers.parse('the nested "{field}" field value starts with "{prefix}"'))
def _nested_starts(redacted_body: dict, field: str, prefix: str) -> None:
    assert str(redacted_body["nested"][field]).startswith(prefix), f"{redacted_body['nested'][field]!r}"


# --- Secret value detection ---

@when(parsers.parse('I check "{value}" for secret-shape'), target_fixture="secret_check")
def _check_secret(value: str) -> bool:
    return looks_like_secret_value(value)


@then("it is identified as a secret")
def _is_secret(secret_check: bool) -> None:
    assert secret_check is True


@then("it is not identified as a secret")
def _is_not_secret(secret_check: bool) -> None:
    assert secret_check is False


# --- Response preview ---

@given(parsers.parse('a response text containing "{text}"'), target_fixture="response_text")
def _response_text(text: str) -> str:
    return text


@when("redact_response_preview processes it", target_fixture="sanitized_text")
def _redact_preview(response_text: str) -> str:
    return redact_response_preview(response_text)


@then(parsers.parse('the resulting text does not contain "{substring}"'))
def _not_contains(sanitized_text: str, substring: str) -> None:
    assert substring not in sanitized_text, f"leak: {substring!r} still in {sanitized_text!r}"


@then(parsers.parse('the resulting text contains "{substring}"'))
def _contains(sanitized_text: str, substring: str) -> None:
    assert substring in sanitized_text
