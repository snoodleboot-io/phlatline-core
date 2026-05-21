"""Unit tests for phlatline.core.project."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from phlatline.core.project import (
    ProjectLoadError,
    ProjectSpec,
    ProjectTargetConfig,
    load_project,
    slugify,
)


# --------------------------------------------------------------------------- #
# slugify
# --------------------------------------------------------------------------- #

class TestSuiteSlugify:
    def test_typical_api_name(self):
        assert slugify("My API v2") == "my-api-v2"

    def test_empty_string_returns_fallback(self):
        assert slugify("") == "target"

    def test_whitespace_only_returns_fallback(self):
        assert slugify("   ") == "target"

    def test_upper_case_with_punctuation(self):
        assert slugify("UPPER CASE!") == "upper-case"

    def test_hello_world(self):
        assert slugify("hello world") == "hello-world"

    def test_single_char(self):
        assert slugify("a") == "a"

    def test_leading_and_trailing_dashes_stripped(self):
        result = slugify("---leading-dashes---")
        assert len(result) > 0
        assert not result.startswith("-")
        assert not result.endswith("-")


# --------------------------------------------------------------------------- #
# load_project — error paths
# --------------------------------------------------------------------------- #

class TestSuiteLoadProjectErrors:
    def test_file_not_found(self, tmp_path):
        missing = tmp_path / "nonexistent.yaml"
        with pytest.raises(ProjectLoadError, match="not found"):
            load_project(str(missing))

    def test_yaml_not_a_dict(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("just a string\n", encoding="utf-8")
        with pytest.raises(ProjectLoadError):
            load_project(str(f))

    def test_invalid_yaml_syntax(self, tmp_path):
        f = tmp_path / "broken.yaml"
        f.write_text("key: [\nunot closed\n", encoding="utf-8")
        with pytest.raises(ProjectLoadError, match="Could not parse"):
            load_project(str(f))

    def test_valid_json_invalid_project_config(self, tmp_path):
        f = tmp_path / "config.json"
        # Valid JSON but missing required "targets" key
        f.write_text(json.dumps({"name": "proj"}), encoding="utf-8")
        with pytest.raises(ProjectLoadError):
            load_project(str(f))

    def test_defaults_not_a_dict(self, tmp_path):
        f = tmp_path / "bad_defaults.yaml"
        f.write_text(
            "defaults: not-a-dict\ntargets:\n  - name: t\n    schema: http://x\n",
            encoding="utf-8",
        )
        with pytest.raises(ProjectLoadError):
            load_project(str(f))

    def test_targets_missing(self, tmp_path):
        f = tmp_path / "no_targets.yaml"
        f.write_text("name: myproject\n", encoding="utf-8")
        with pytest.raises(ProjectLoadError):
            load_project(str(f))

    def test_targets_contains_non_dict_entry(self, tmp_path):
        f = tmp_path / "bad_target.yaml"
        content = {"targets": ["just-a-string"]}
        f.write_text(yaml.dump(content), encoding="utf-8")
        with pytest.raises(ProjectLoadError):
            load_project(str(f))

    def test_duplicate_target_names_raises(self, tmp_path):
        f = tmp_path / "dupes.yaml"
        content = {
            "targets": [
                {"name": "My API", "schema": "http://a.test/openapi.json"},
                {"name": "my api", "schema": "http://b.test/openapi.json"},
            ]
        }
        f.write_text(yaml.dump(content), encoding="utf-8")
        with pytest.raises(ProjectLoadError, match="Duplicate"):
            load_project(str(f))


# --------------------------------------------------------------------------- #
# load_project — success paths
# --------------------------------------------------------------------------- #

def _minimal_yaml(tmp_path: Path, extra: dict | None = None) -> Path:
    data: dict = {
        "targets": [{"name": "my-api", "schema": "http://api.test/openapi.json"}]
    }
    if extra:
        data.update(extra)
    f = tmp_path / "project.yaml"
    f.write_text(yaml.dump(data), encoding="utf-8")
    return f


class TestSuiteLoadProjectSuccess:
    def test_minimal_yaml_returns_project_spec(self, tmp_path):
        f = _minimal_yaml(tmp_path)
        spec = load_project(str(f))
        assert isinstance(spec, ProjectSpec)
        assert len(spec.targets) == 1
        assert spec.targets[0].name == "my-api"

    def test_name_parsed(self, tmp_path):
        f = _minimal_yaml(tmp_path, {"name": "test-project"})
        spec = load_project(str(f))
        assert spec.name == "test-project"

    def test_parallel_parsed(self, tmp_path):
        f = _minimal_yaml(tmp_path, {"parallel": True})
        spec = load_project(str(f))
        assert spec.parallel is True

    def test_max_parallel_targets_parsed(self, tmp_path):
        f = _minimal_yaml(tmp_path, {"max_parallel_targets": 8})
        spec = load_project(str(f))
        assert spec.max_parallel_targets == 8

    def test_json_file_supported(self, tmp_path):
        data = {
            "name": "json-project",
            "targets": [{"name": "svc", "schema": "http://svc.test/openapi.json"}],
        }
        f = tmp_path / "project.json"
        f.write_text(json.dumps(data), encoding="utf-8")
        spec = load_project(str(f))
        assert spec.name == "json-project"
        assert spec.targets[0].name == "svc"


# --------------------------------------------------------------------------- #
# _merge_defaults_into_targets (tested via load_project)
# --------------------------------------------------------------------------- #

class TestSuiteMergeDefaults:
    def test_default_base_url_appears_in_target(self, tmp_path):
        data = {
            "defaults": {"base_url": "https://default.test"},
            "targets": [{"name": "svc", "schema": "http://svc.test/openapi.json"}],
        }
        f = tmp_path / "project.yaml"
        f.write_text(yaml.dump(data), encoding="utf-8")
        spec = load_project(str(f))
        assert spec.targets[0].base_url == "https://default.test"

    def test_per_target_field_overrides_default(self, tmp_path):
        data = {
            "defaults": {"base_url": "https://default.test"},
            "targets": [
                {
                    "name": "svc",
                    "schema": "http://svc.test/openapi.json",
                    "base_url": "https://override.test",
                }
            ],
        }
        f = tmp_path / "project.yaml"
        f.write_text(yaml.dump(data), encoding="utf-8")
        spec = load_project(str(f))
        assert spec.targets[0].base_url == "https://override.test"


# --------------------------------------------------------------------------- #
# ProjectTargetConfig.to_spec
# --------------------------------------------------------------------------- #

class TestSuiteToSpec:
    def test_to_spec_maps_fields_correctly(self):
        cfg = ProjectTargetConfig(
            name="my-api",
            schema="http://api.test/openapi.json",
            base_url="https://api.test",
            auth={"type": "bearer", "token": "tok"},
        )
        spec = cfg.to_spec()
        assert spec.name == "my-api"
        assert spec.schema_source == "http://api.test/openapi.json"
        assert spec.base_url == "https://api.test"
        assert spec.auth == {"type": "bearer", "token": "tok"}
        assert spec.fuzz_enabled is True  # default

    def test_fuzz_true_maps_to_fuzz_enabled_true(self):
        cfg = ProjectTargetConfig(
            name="svc",
            schema="http://svc.test/openapi.json",
            fuzz=True,
        )
        assert cfg.to_spec().fuzz_enabled is True

    def test_fuzz_false_maps_to_fuzz_enabled_false(self):
        cfg = ProjectTargetConfig(
            name="svc",
            schema="http://svc.test/openapi.json",
            fuzz=False,
        )
        assert cfg.to_spec().fuzz_enabled is False
