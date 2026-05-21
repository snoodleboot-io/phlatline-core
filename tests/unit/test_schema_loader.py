"""Unit tests for phlatline.core.schema_loader."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
import yaml

from phlatline.core.schema_loader import (
    SchemaLoadError,
    _hint_from_content_type,
    _looks_like_html,
    _url_points_at_schema_file,
    load_schema,
    resolve_base_url,
)

_MINIMAL_SCHEMA = {"openapi": "3.0.0", "info": {"title": "T", "version": "1"}, "paths": {}}
_MINIMAL_JSON = json.dumps(_MINIMAL_SCHEMA)
_MINIMAL_YAML = yaml.dump(_MINIMAL_SCHEMA)


# --------------------------------------------------------------------------- #
# _looks_like_html
# --------------------------------------------------------------------------- #

class TestSuiteLooksLikeHtml:
    def test_html_content_type(self):
        assert _looks_like_html("text/html; charset=utf-8") is True

    def test_json_content_type(self):
        assert _looks_like_html("application/json") is False

    def test_empty_content_type(self):
        assert _looks_like_html("") is False


# --------------------------------------------------------------------------- #
# _url_points_at_schema_file
# --------------------------------------------------------------------------- #

class TestSuiteUrlPointsAtSchemaFile:
    def test_json_url(self):
        assert _url_points_at_schema_file("http://api.test/openapi.json") is True

    def test_yaml_url(self):
        assert _url_points_at_schema_file("http://api.test/spec.yaml") is True

    def test_yml_url(self):
        assert _url_points_at_schema_file("http://api.test/spec.yml") is True

    def test_html_url(self):
        assert _url_points_at_schema_file("http://api.test/docs") is False

    def test_trailing_slash_stripped_so_json_detected(self):
        # rstrip("/") makes "openapi.json/" → "openapi.json" which IS a schema URL
        assert _url_points_at_schema_file("http://api.test/openapi.json/") is True


# --------------------------------------------------------------------------- #
# _hint_from_content_type
# --------------------------------------------------------------------------- #

class TestSuiteHintFromContentType:
    def test_json_content_type(self):
        assert _hint_from_content_type("application/json") == ".json"

    def test_yaml_content_type(self):
        assert _hint_from_content_type("application/yaml") in {".yaml", ".yml"}

    def test_unknown_content_type(self):
        assert _hint_from_content_type("text/plain") == ""

    def test_empty_content_type(self):
        assert _hint_from_content_type("") == ""


# --------------------------------------------------------------------------- #
# load_schema — file paths
# --------------------------------------------------------------------------- #

class TestSuiteLoadSchemaFile:
    def test_load_json_file(self, tmp_path: Path):
        p = tmp_path / "spec.json"
        p.write_text(_MINIMAL_JSON, encoding="utf-8")
        result = load_schema(str(p))
        assert result["openapi"] == "3.0.0"

    def test_load_yaml_file(self, tmp_path: Path):
        p = tmp_path / "spec.yaml"
        p.write_text(_MINIMAL_YAML, encoding="utf-8")
        result = load_schema(str(p))
        assert result["openapi"] == "3.0.0"

    def test_nonexistent_file_raises(self):
        with pytest.raises(SchemaLoadError, match="not found"):
            load_schema("/nonexistent/spec.json")

    def test_invalid_json_raises(self, tmp_path: Path):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(SchemaLoadError, match="Invalid JSON"):
            load_schema(str(p))

    def test_invalid_yaml_raises(self, tmp_path: Path):
        p = tmp_path / "bad.yaml"
        p.write_text("key: [\nbroken", encoding="utf-8")
        with pytest.raises(SchemaLoadError, match="Invalid YAML"):
            load_schema(str(p))

    def test_yaml_not_dict_raises(self, tmp_path: Path):
        p = tmp_path / "list.yaml"
        p.write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(SchemaLoadError, match="mapping"):
            load_schema(str(p))

    def test_unknown_suffix_tries_json_first(self, tmp_path: Path):
        p = tmp_path / "spec.txt"
        p.write_text(_MINIMAL_JSON, encoding="utf-8")
        result = load_schema(str(p))
        assert result["openapi"] == "3.0.0"

    def test_unknown_suffix_falls_back_to_yaml(self, tmp_path: Path):
        p = tmp_path / "spec.txt"
        p.write_text(_MINIMAL_YAML, encoding="utf-8")
        result = load_schema(str(p))
        assert result["openapi"] == "3.0.0"


# --------------------------------------------------------------------------- #
# load_schema — URL paths (mocked with respx)
# --------------------------------------------------------------------------- #

class TestSuiteLoadSchemaUrl:
    @respx.mock
    def test_load_json_from_url(self):
        respx.get("http://api.test/openapi.json").mock(
            return_value=httpx.Response(200, json=_MINIMAL_SCHEMA,
                                        headers={"content-type": "application/json"})
        )
        result = load_schema("http://api.test/openapi.json")
        assert result["openapi"] == "3.0.0"

    @respx.mock
    def test_html_response_retries_openapi_path(self):
        respx.get("http://api.test/docs").mock(
            return_value=httpx.Response(200, text="<html></html>",
                                        headers={"content-type": "text/html"})
        )
        respx.get("http://api.test/docs/openapi.json").mock(
            return_value=httpx.Response(200, json=_MINIMAL_SCHEMA,
                                        headers={"content-type": "application/json"})
        )
        result = load_schema("http://api.test/docs")
        assert result["openapi"] == "3.0.0"

    @respx.mock
    def test_http_error_raises_schema_load_error(self):
        respx.get("http://api.test/openapi.json").mock(
            return_value=httpx.Response(404)
        )
        with pytest.raises(Exception):
            load_schema("http://api.test/openapi.json")


# --------------------------------------------------------------------------- #
# resolve_base_url
# --------------------------------------------------------------------------- #

class TestSuiteResolveBaseUrl:
    def test_override_wins_over_servers(self):
        schema = {"servers": [{"url": "http://schema-server.test"}]}
        assert resolve_base_url(schema, "http://override.test") == "http://override.test"

    def test_first_server_used_when_no_override(self):
        schema = {"servers": [{"url": "http://api.test"}]}
        assert resolve_base_url(schema) == "http://api.test"

    def test_trailing_slash_stripped(self):
        schema = {"servers": [{"url": "http://api.test/"}]}
        assert resolve_base_url(schema) == "http://api.test"

    def test_empty_servers_returns_empty_string(self):
        assert resolve_base_url({}) == ""
        assert resolve_base_url({"servers": []}) == ""

    def test_override_trailing_slash_stripped(self):
        assert resolve_base_url({}, "http://api.test/") == "http://api.test"
