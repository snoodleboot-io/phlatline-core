"""Authentication — Strategy pattern for each supported auth scheme.

Each auth scheme is a concrete AuthStrategy that:
    1. Accepts a Pydantic config model validated at construction time
    2. Produces an AuthContext ready to attach to HTTP requests

An AuthStrategyFactory dispatches on AuthType to pick the right strategy.
No string literals, no dict-sniffing — every shape is validated up front.
"""
from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr

from phlatline.config.enums import ApiKeyLocation, AuthType, OAuth2Flow
from phlatline.config.settings import settings


# --------------------------------------------------------------------------- #
# AuthContext — the material auth strategies produce
# --------------------------------------------------------------------------- #

class AuthContext(BaseModel):
    """Headers, query params, and cookies to attach to requests."""

    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, str] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)

    def merged_with(self, extras: "AuthExtras") -> "AuthContext":
        return AuthContext(
            headers={**self.headers, **extras.headers},
            query_params={**self.query_params, **extras.query_params},
            cookies={**self.cookies, **extras.cookies},
        )


class AuthExtras(BaseModel):
    """Free-form extra material (custom headers, cookies, query) that can be
    layered on top of any base auth."""

    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, str] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Per-scheme Pydantic configs
# --------------------------------------------------------------------------- #

class _AuthConfigBase(BaseModel):
    """Common base — permits extra keys for 'headers'/'cookies'/'query' extras."""

    model_config = ConfigDict(extra="allow")

    headers: dict[str, str] | None = None
    cookies: dict[str, str] | None = None
    query: dict[str, str] | None = None


class BearerAuthConfig(_AuthConfigBase):
    type: AuthType = Field(default=AuthType.BEARER)
    token: SecretStr


class BasicAuthConfig(_AuthConfigBase):
    type: AuthType = Field(default=AuthType.BASIC)
    username: str
    password: SecretStr


class ApiKeyAuthConfig(_AuthConfigBase):
    type: AuthType = Field(default=AuthType.API_KEY)
    name: str = Field(min_length=1, description="Parameter/header name.")
    value: SecretStr
    in_: ApiKeyLocation = Field(
        default=ApiKeyLocation.HEADER,
        alias="in",
        description="Where to place the key.",
    )

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class OAuth2AuthConfig(_AuthConfigBase):
    type: AuthType = Field(default=AuthType.OAUTH2)
    flow: OAuth2Flow = Field(default=OAuth2Flow.CLIENT_CREDENTIALS)
    token_url: HttpUrl
    client_id: str | None = None
    client_secret: SecretStr | None = None
    username: str | None = None
    password: SecretStr | None = None
    scope: str | None = None
    token_headers: dict[str, str] | None = None


class CustomAuthConfig(_AuthConfigBase):
    """No base credentials — just `headers`/`cookies`/`query` extras."""

    type: AuthType = Field(default=AuthType.CUSTOM)


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #

class AuthError(Exception):
    """Raised when auth config cannot be resolved."""


# --------------------------------------------------------------------------- #
# Strategy base + concrete strategies
# --------------------------------------------------------------------------- #

class AuthStrategy(ABC):
    """Produces an AuthContext from a validated config."""

    @abstractmethod
    def build_context(self) -> AuthContext: ...

    @staticmethod
    def _extras_from(cfg: _AuthConfigBase) -> AuthExtras:
        return AuthExtras(
            headers=dict(cfg.headers or {}),
            query_params=dict(cfg.query or {}),
            cookies=dict(cfg.cookies or {}),
        )


class BearerStrategy(AuthStrategy):
    def __init__(self, cfg: BearerAuthConfig) -> None:
        self._cfg = cfg

    def build_context(self) -> AuthContext:
        base = AuthContext(
            headers={"Authorization": f"Bearer {self._cfg.token.get_secret_value()}"}
        )
        return base.merged_with(self._extras_from(self._cfg))


class BasicStrategy(AuthStrategy):
    def __init__(self, cfg: BasicAuthConfig) -> None:
        self._cfg = cfg

    def build_context(self) -> AuthContext:
        raw = f"{self._cfg.username}:{self._cfg.password.get_secret_value()}".encode()
        encoded = base64.b64encode(raw).decode()
        base = AuthContext(headers={"Authorization": f"Basic {encoded}"})
        return base.merged_with(self._extras_from(self._cfg))


class ApiKeyStrategy(AuthStrategy):
    def __init__(self, cfg: ApiKeyAuthConfig) -> None:
        self._cfg = cfg

    def build_context(self) -> AuthContext:
        value = self._cfg.value.get_secret_value()
        ctx = AuthContext()
        match self._cfg.in_:
            case ApiKeyLocation.HEADER:
                ctx = AuthContext(headers={self._cfg.name: value})
            case ApiKeyLocation.QUERY:
                ctx = AuthContext(query_params={self._cfg.name: value})
            case ApiKeyLocation.COOKIE:
                ctx = AuthContext(cookies={self._cfg.name: value})
        return ctx.merged_with(self._extras_from(self._cfg))


class OAuth2Strategy(AuthStrategy):
    def __init__(self, cfg: OAuth2AuthConfig) -> None:
        self._cfg = cfg

    def build_context(self) -> AuthContext:
        token = self._fetch_token()
        base = AuthContext(headers={"Authorization": f"Bearer {token}"})
        return base.merged_with(self._extras_from(self._cfg))

    def _fetch_token(self) -> str:
        data = self._build_token_request_payload()
        try:
            with httpx.Client(timeout=settings.execution.request_timeout_s) as client:
                resp = client.post(
                    str(self._cfg.token_url),
                    data=data,
                    headers=self._cfg.token_headers or {},
                )
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as e:
            raise AuthError(f"OAuth2 token fetch failed: {e}") from e

        token = payload.get("access_token")
        if not token:
            raise AuthError(f"OAuth2 response missing access_token: {payload}")
        return str(token)

    def _build_token_request_payload(self) -> dict[str, str]:
        data: dict[str, str] = {"grant_type": self._cfg.flow.value}
        match self._cfg.flow:
            case OAuth2Flow.CLIENT_CREDENTIALS:
                if self._cfg.client_id:
                    data["client_id"] = self._cfg.client_id
                if self._cfg.client_secret:
                    data["client_secret"] = self._cfg.client_secret.get_secret_value()
            case OAuth2Flow.PASSWORD:
                if self._cfg.username:
                    data["username"] = self._cfg.username
                if self._cfg.password:
                    data["password"] = self._cfg.password.get_secret_value()
                if self._cfg.client_id:
                    data["client_id"] = self._cfg.client_id
                if self._cfg.client_secret:
                    data["client_secret"] = self._cfg.client_secret.get_secret_value()
        if self._cfg.scope:
            data["scope"] = self._cfg.scope
        return data


class CustomStrategy(AuthStrategy):
    def __init__(self, cfg: CustomAuthConfig) -> None:
        self._cfg = cfg

    def build_context(self) -> AuthContext:
        return AuthContext().merged_with(self._extras_from(self._cfg))


# --------------------------------------------------------------------------- #
# Factory — dispatches on AuthType
# --------------------------------------------------------------------------- #

_STRATEGY_BY_TYPE: dict[AuthType, tuple[type[_AuthConfigBase], type[AuthStrategy]]] = {
    AuthType.BEARER:  (BearerAuthConfig,  BearerStrategy),
    AuthType.BASIC:   (BasicAuthConfig,   BasicStrategy),
    AuthType.API_KEY: (ApiKeyAuthConfig,  ApiKeyStrategy),
    AuthType.OAUTH2:  (OAuth2AuthConfig,  OAuth2Strategy),
    AuthType.CUSTOM:  (CustomAuthConfig,  CustomStrategy),
}


def build_auth_context(raw_config: dict[str, Any] | None) -> AuthContext:
    """Resolve a raw auth config into an AuthContext.

    None or empty config yields an empty context (no auth).
    """
    if not raw_config:
        return AuthContext()

    raw_type = raw_config.get("type")
    if raw_type is None:
        raise AuthError("auth config missing required 'type' field")

    try:
        auth_type = AuthType(str(raw_type).lower())
    except ValueError as e:
        valid = ", ".join(t.value for t in AuthType)
        raise AuthError(f"Unknown auth type {raw_type!r}; expected one of: {valid}") from e

    config_cls, strategy_cls = _STRATEGY_BY_TYPE[auth_type]
    try:
        cfg = config_cls.model_validate(raw_config)
    except Exception as e:
        raise AuthError(f"Invalid {auth_type.value} auth config: {e}") from e

    return strategy_cls(cfg).build_context()  # type: ignore[arg-type]
