"""Multi-target project configuration.

A project YAML lists one or more targets, each producing its own report.
Top-level `defaults:` is merged with each target's own keys before validation.

The whole config is a Pydantic model — we get validation, type coercion,
and helpful error messages for free.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, PositiveFloat, PositiveInt

from phlatline.sdk.models import TargetSpec


class ProjectLoadError(Exception):
    """Raised when a project config cannot be parsed or validated."""


# --------------------------------------------------------------------------- #
# Slug helper — filesystem-safe target names
# --------------------------------------------------------------------------- #

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
_SLUG_FALLBACK = "target"


def slugify(name: str) -> str:
    """Produce a filesystem-safe slug from a target name."""
    slug = _SLUG_PATTERN.sub("-", name.lower()).strip("-")
    return slug or _SLUG_FALLBACK


# --------------------------------------------------------------------------- #
# Target config (ingested from YAML; different from SDK's TargetSpec in that
# it carries run-level tunables that the runner uses to shape execution)
# --------------------------------------------------------------------------- #

class ProjectTargetConfig(BaseModel):
    """A target entry in a project file, with defaults already merged."""

    name: str = Field(min_length=1)
    schema_source: str = Field(alias="schema", min_length=1)
    base_url: str | None = None
    auth: dict[str, Any] | None = None
    request_timeout_s: PositiveFloat = 30.0
    fuzz: bool = True
    fuzz_examples: PositiveInt = 15
    verify_ssl: bool = True

    # Concurrency is intentionally NOT on this model. In OSS it's unused;
    # EE's ConcurrentExecutor reads its own settings.

    model_config = {"populate_by_name": True, "extra": "allow"}

    def to_spec(self) -> TargetSpec:
        return TargetSpec(
            name=self.name,
            schema_source=self.schema_source,
            base_url=self.base_url,
            auth=self.auth,
            fuzz_enabled=self.fuzz,
        )


# --------------------------------------------------------------------------- #
# Project-level config
# --------------------------------------------------------------------------- #

_DEFAULT_PROJECT_NAME = "phlatline-project"
_DEFAULT_MAX_PARALLEL_TARGETS = 4


class ProjectSpec(BaseModel):
    """A parsed multi-target project."""

    name: str = Field(default=_DEFAULT_PROJECT_NAME, min_length=1)
    parallel: bool = False
    max_parallel_targets: PositiveInt = _DEFAULT_MAX_PARALLEL_TARGETS
    targets: list[ProjectTargetConfig] = Field(min_length=1)


# --------------------------------------------------------------------------- #
# Loader
# --------------------------------------------------------------------------- #

_YAML_SUFFIXES: frozenset[str] = frozenset({".yaml", ".yml"})


def load_project(path: str) -> ProjectSpec:
    """Load and validate a project config from YAML or JSON."""
    p = Path(path)
    if not p.exists():
        raise ProjectLoadError(f"Project file not found: {path}")

    raw = _parse_file(p)
    if not isinstance(raw, dict):
        raise ProjectLoadError("Project file must be a mapping at the top level")

    merged = _merge_defaults_into_targets(raw)

    try:
        spec = ProjectSpec.model_validate(merged)
    except Exception as e:
        raise ProjectLoadError(f"Invalid project config: {e}") from e

    _assert_unique_slugs(spec.targets)
    return spec


def _parse_file(p: Path) -> Any:
    text = p.read_text(encoding="utf-8")
    try:
        if p.suffix in _YAML_SUFFIXES:
            return yaml.safe_load(text) or {}
        return json.loads(text)
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        raise ProjectLoadError(f"Could not parse project file: {e}") from e


def _merge_defaults_into_targets(raw: dict[str, Any]) -> dict[str, Any]:
    """Shallow-merge top-level `defaults:` into each target entry.

    Per-target keys win. Returns a new dict; does not mutate input.
    """
    defaults = raw.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise ProjectLoadError("'defaults' must be a mapping")

    targets_raw = raw.get("targets")
    if not isinstance(targets_raw, list):
        raise ProjectLoadError("Project must declare at least one target under 'targets'")

    merged_targets: list[dict[str, Any]] = []
    for i, t in enumerate(targets_raw):
        if not isinstance(t, dict):
            raise ProjectLoadError(f"Target #{i + 1} must be a mapping")
        merged_targets.append({**defaults, **t})

    return {
        "name": raw.get("name", _DEFAULT_PROJECT_NAME),
        "parallel": raw.get("parallel", False),
        "max_parallel_targets": raw.get(
            "max_parallel_targets", _DEFAULT_MAX_PARALLEL_TARGETS
        ),
        "targets": merged_targets,
    }


def _assert_unique_slugs(targets: list[ProjectTargetConfig]) -> None:
    seen: set[str] = set()
    for t in targets:
        slug = slugify(t.name)
        if slug in seen:
            raise ProjectLoadError(f"Duplicate target name (slug collision): {t.name}")
        seen.add(slug)
