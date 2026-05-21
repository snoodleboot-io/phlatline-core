"""Unit tests for SequentialExecutor internal helpers."""
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from phlatline.config.enums import HttpMethod, TestCategory
from phlatline.core.auth import AuthContext
from phlatline.core.sequential_executor import SequentialExecutor
from phlatline.sdk.models import TestCase


def _make_case(**overrides) -> TestCase:
    defaults = dict(
        test_id="t1",
        category=TestCategory.HAPPY,
        method=HttpMethod.GET,
        path="/ping",
        path_template="/ping",
        operation_id="ping",
        summary="Ping",
        body=None,
        send_auth=True,
    )
    defaults.update(overrides)
    return TestCase(**defaults)


# --------------------------------------------------------------------------- #
# _body_kwargs
# --------------------------------------------------------------------------- #

class TestSuiteBodyKwargs:
    def test_none_body_returns_empty(self):
        case = _make_case(body=None)
        assert SequentialExecutor._body_kwargs(case, {}) == {}

    def test_dict_body_uses_json(self):
        case = _make_case(body={"key": "val"})
        assert SequentialExecutor._body_kwargs(case, {}) == {"json": {"key": "val"}}

    def test_list_body_uses_json(self):
        case = _make_case(body=[1, 2, 3])
        assert SequentialExecutor._body_kwargs(case, {}) == {"json": [1, 2, 3]}

    def test_string_body_uses_content_bytes(self):
        case = _make_case(body="plain text")
        result = SequentialExecutor._body_kwargs(case, {})
        assert result == {"content": b"plain text"}

    def test_string_body_sets_content_type_when_absent(self):
        case = _make_case(body="plain text")
        headers: dict[str, str] = {}
        SequentialExecutor._body_kwargs(case, headers)
        assert headers["Content-Type"] == "text/plain"

    def test_string_body_does_not_override_existing_content_type(self):
        case = _make_case(body="data")
        headers = {"Content-Type": "application/octet-stream"}
        SequentialExecutor._body_kwargs(case, headers)
        assert headers["Content-Type"] == "application/octet-stream"


# --------------------------------------------------------------------------- #
# _merge_auth
# --------------------------------------------------------------------------- #

class TestSuiteMergeAuth:
    def test_send_auth_true_merges_auth_headers(self):
        case = _make_case(send_auth=True)
        auth = AuthContext(headers={"Authorization": "Bearer tok"})
        headers, _, _ = SequentialExecutor._merge_auth(case, auth)
        assert headers["Authorization"] == "Bearer tok"

    def test_send_auth_false_skips_auth(self):
        case = _make_case(send_auth=False)
        auth = AuthContext(headers={"Authorization": "Bearer tok"})
        headers, _, _ = SequentialExecutor._merge_auth(case, auth)
        assert "Authorization" not in headers


# --------------------------------------------------------------------------- #
# _preview
# --------------------------------------------------------------------------- #

class TestSuitePreview:
    def test_truncates_long_response(self):
        mock_resp = MagicMock()
        long_text = "x" * 10000
        mock_resp.text = long_text
        result = SequentialExecutor._preview(mock_resp)
        assert result.endswith("…")

    def test_returns_binary_placeholder_on_decode_error(self):
        mock_resp = MagicMock()
        type(mock_resp).text = PropertyMock(side_effect=Exception("decode error"))
        result = SequentialExecutor._preview(mock_resp)
        assert result == "<binary response>"
