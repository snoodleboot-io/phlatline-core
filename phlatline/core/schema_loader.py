"""Load OpenAPI schemas from a file path or URL (including FastAPI /openapi.json)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import yaml

from phlatline.config.settings import settings


class SchemaLoadError(Exception):
    """Raised when a schema cannot be loaded or parsed."""


_FASTAPI_DEFAULT_PATH = "/openapi.json"
_JSON_SUFFIXES = {".json"}
_YAML_SUFFIXES = {".yaml", ".yml"}
_URL_PREFIXES = ("http://", "https://")


def load_schema(source: str) -> dict[str, Any]:
    """Load an OpenAPI schema from a local file or remote URL.

    For URLs, tries the URL as given, then appends /openapi.json if the
    first fetch yields HTML (FastAPI's /docs page).
    """
    if source.startswith(_URL_PREFIXES):
        return _load_from_url(source)
    return _load_from_file(source)


def _load_from_file(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise SchemaLoadError(f"Schema file not found: {path}")
    return _parse(p.read_text(encoding="utf-8"), hint=p.suffix)


def _load_from_url(url: str) -> dict[str, Any]:
    timeout = settings.execution.request_timeout_s
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "").lower()

        if _looks_like_html(ctype) and not _url_points_at_schema_file(url):
            resp = client.get(url.rstrip("/") + _FASTAPI_DEFAULT_PATH)
            resp.raise_for_status()
            ctype = resp.headers.get("content-type", "").lower()

        hint = _hint_from_content_type(ctype)
        return _parse(resp.text, hint=hint)


def _looks_like_html(content_type: str) -> bool:
    return "html" in content_type


def _url_points_at_schema_file(url: str) -> bool:
    trimmed = url.rstrip("/")
    return any(trimmed.endswith(suffix) for suffix in _JSON_SUFFIXES | _YAML_SUFFIXES)


def _hint_from_content_type(content_type: str) -> str:
    if "json" in content_type:
        return next(iter(_JSON_SUFFIXES))
    if "yaml" in content_type:
        return next(iter(_YAML_SUFFIXES))
    return ""


def _parse(text: str, hint: str = "") -> dict[str, Any]:
    if hint in _JSON_SUFFIXES:
        return _parse_json(text)
    if hint in _YAML_SUFFIXES:
        return _parse_yaml(text)

    # Unknown suffix — try JSON then YAML
    try:
        return _parse_json(text)
    except SchemaLoadError:
        return _parse_yaml(text)


def _parse_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise SchemaLoadError(f"Invalid JSON schema: {e}") from e


def _parse_yaml(text: str) -> dict[str, Any]:
    try:
        result = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise SchemaLoadError(f"Invalid YAML schema: {e}") from e
    if not isinstance(result, dict):
        raise SchemaLoadError("Schema did not parse to a mapping")
    return result


def resolve_base_url(schema: dict[str, Any], override: str | None = None) -> str:
    """Pick a base URL for requests: override > first declared server > empty."""
    if override:
        return override.rstrip("/")
    servers = schema.get("servers") or []
    if servers and isinstance(servers[0], dict):
        return str(servers[0].get("url", "")).rstrip("/")
    return ""
