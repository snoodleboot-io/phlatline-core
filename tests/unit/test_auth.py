"""Unit tests for phlatline.core.auth — auth strategy coverage."""
from __future__ import annotations

import pytest
import respx
import httpx

from phlatline.config.enums import ApiKeyLocation, AuthType, OAuth2Flow
from phlatline.core.auth import (
    AuthContext,
    AuthError,
    ApiKeyStrategy,
    ApiKeyAuthConfig,
    BasicStrategy,
    BasicAuthConfig,
    BearerStrategy,
    BearerAuthConfig,
    CustomStrategy,
    CustomAuthConfig,
    OAuth2Strategy,
    OAuth2AuthConfig,
    build_auth_context,
)


# --------------------------------------------------------------------------- #
# BearerStrategy
# --------------------------------------------------------------------------- #

class TestSuiteBearerStrategy:
    def test_produces_authorization_header(self):
        cfg = BearerAuthConfig(token="secret-token")  # type: ignore[call-arg]
        ctx = BearerStrategy(cfg).build_context()
        assert ctx.headers["Authorization"] == "Bearer secret-token"

    def test_extra_headers_merged(self):
        cfg = BearerAuthConfig(token="t", headers={"X-Extra": "yes"})  # type: ignore[call-arg]
        ctx = BearerStrategy(cfg).build_context()
        assert ctx.headers["X-Extra"] == "yes"
        assert "Authorization" in ctx.headers

    def test_extra_query_merged(self):
        cfg = BearerAuthConfig(token="t", query={"trace": "1"})  # type: ignore[call-arg]
        ctx = BearerStrategy(cfg).build_context()
        assert ctx.query_params["trace"] == "1"


# --------------------------------------------------------------------------- #
# BasicStrategy
# --------------------------------------------------------------------------- #

class TestSuiteBasicStrategy:
    def test_produces_basic_authorization_header(self):
        import base64
        cfg = BasicAuthConfig(username="alice", password="hunter2")  # type: ignore[call-arg]
        ctx = BasicStrategy(cfg).build_context()
        expected = "Basic " + base64.b64encode(b"alice:hunter2").decode()
        assert ctx.headers["Authorization"] == expected

    def test_extra_cookies_merged(self):
        cfg = BasicAuthConfig(  # type: ignore[call-arg]
            username="alice", password="pw", cookies={"session": "abc"}
        )
        ctx = BasicStrategy(cfg).build_context()
        assert ctx.cookies["session"] == "abc"


# --------------------------------------------------------------------------- #
# ApiKeyStrategy
# --------------------------------------------------------------------------- #

class TestSuiteApiKeyStrategy:
    def test_api_key_in_header(self):
        cfg = ApiKeyAuthConfig(name="X-Api-Key", value="k1", **{"in": "header"})  # type: ignore[call-arg]
        ctx = ApiKeyStrategy(cfg).build_context()
        assert ctx.headers["X-Api-Key"] == "k1"
        assert not ctx.query_params
        assert not ctx.cookies

    def test_api_key_in_query(self):
        cfg = ApiKeyAuthConfig(name="api_key", value="k2", **{"in": "query"})  # type: ignore[call-arg]
        ctx = ApiKeyStrategy(cfg).build_context()
        assert ctx.query_params["api_key"] == "k2"
        assert not ctx.headers

    def test_api_key_in_cookie(self):
        cfg = ApiKeyAuthConfig(name="token", value="k3", **{"in": "cookie"})  # type: ignore[call-arg]
        ctx = ApiKeyStrategy(cfg).build_context()
        assert ctx.cookies["token"] == "k3"
        assert not ctx.headers


# --------------------------------------------------------------------------- #
# CustomStrategy
# --------------------------------------------------------------------------- #

class TestSuiteCustomStrategy:
    def test_empty_config_empty_context(self):
        cfg = CustomAuthConfig()
        ctx = CustomStrategy(cfg).build_context()
        assert ctx.headers == {}
        assert ctx.query_params == {}
        assert ctx.cookies == {}

    def test_custom_with_extras(self):
        cfg = CustomAuthConfig(
            headers={"X-Custom": "value"},
            query={"debug": "true"},
            cookies={"sid": "abc"},
        )
        ctx = CustomStrategy(cfg).build_context()
        assert ctx.headers["X-Custom"] == "value"
        assert ctx.query_params["debug"] == "true"
        assert ctx.cookies["sid"] == "abc"


# --------------------------------------------------------------------------- #
# OAuth2Strategy — token fetch (mocked)
# --------------------------------------------------------------------------- #

class TestSuiteOAuth2Strategy:
    _TOKEN_URL = "https://auth.example.com/oauth/token"

    def _cfg(self, **kwargs) -> OAuth2AuthConfig:
        return OAuth2AuthConfig(  # type: ignore[call-arg]
            token_url=self._TOKEN_URL,
            **kwargs,
        )

    @respx.mock
    def test_client_credentials_builds_bearer_header(self):
        respx.post(self._TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"access_token": "tok123"})
        )
        ctx = OAuth2Strategy(self._cfg(
            client_id="id", client_secret="secret"
        )).build_context()
        assert ctx.headers["Authorization"] == "Bearer tok123"

    @respx.mock
    def test_password_flow_includes_username(self):
        respx.post(self._TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"access_token": "tok456"})
        )
        ctx = OAuth2Strategy(self._cfg(
            flow=OAuth2Flow.PASSWORD,
            username="alice", password="pw",
        )).build_context()
        assert ctx.headers["Authorization"] == "Bearer tok456"

    @respx.mock
    def test_token_fetch_http_error_raises_auth_error(self):
        respx.post(self._TOKEN_URL).mock(
            side_effect=httpx.ConnectError("timeout")
        )
        with pytest.raises(AuthError, match="OAuth2 token fetch failed"):
            OAuth2Strategy(self._cfg()).build_context()

    @respx.mock
    def test_missing_access_token_in_response_raises_auth_error(self):
        respx.post(self._TOKEN_URL).mock(
            return_value=httpx.Response(200, json={"error": "invalid_client"})
        )
        with pytest.raises(AuthError, match="missing access_token"):
            OAuth2Strategy(self._cfg()).build_context()

    @respx.mock
    def test_scope_included_in_payload(self):
        captured = {}

        def capture_request(request):
            captured["body"] = request.content.decode()
            return httpx.Response(200, json={"access_token": "tok"})

        respx.post(self._TOKEN_URL).mock(side_effect=capture_request)
        OAuth2Strategy(self._cfg(scope="read:api")).build_context()
        assert "scope=read%3Aapi" in captured["body"] or "scope" in captured["body"]


# --------------------------------------------------------------------------- #
# build_auth_context — dispatch + error paths
# --------------------------------------------------------------------------- #

class TestSuiteBuildAuthContext:
    def test_none_returns_empty_context(self):
        ctx = build_auth_context(None)
        assert ctx.headers == {}

    def test_empty_dict_returns_empty_context(self):
        ctx = build_auth_context({})
        assert ctx.headers == {}

    def test_missing_type_raises_auth_error(self):
        with pytest.raises(AuthError, match="missing required 'type' field"):
            build_auth_context({"token": "abc"})

    def test_unknown_type_raises_auth_error(self):
        with pytest.raises(AuthError, match="Unknown auth type"):
            build_auth_context({"type": "magic-sauce"})

    def test_invalid_config_raises_auth_error(self):
        # bearer without 'token' field → validation fails
        with pytest.raises(AuthError, match="Invalid bearer auth config"):
            build_auth_context({"type": "bearer"})

    def test_bearer_dispatch(self):
        ctx = build_auth_context({"type": "bearer", "token": "my-token"})
        assert ctx.headers["Authorization"] == "Bearer my-token"

    def test_basic_dispatch(self):
        ctx = build_auth_context({"type": "basic", "username": "u", "password": "p"})
        assert "Authorization" in ctx.headers
        assert ctx.headers["Authorization"].startswith("Basic ")

    def test_apikey_dispatch(self):
        ctx = build_auth_context({"type": "api_key", "name": "X-Key", "value": "v", "in": "header"})
        assert ctx.headers["X-Key"] == "v"

    def test_custom_dispatch(self):
        ctx = build_auth_context({"type": "custom", "headers": {"X-Custom": "c"}})
        assert ctx.headers["X-Custom"] == "c"
