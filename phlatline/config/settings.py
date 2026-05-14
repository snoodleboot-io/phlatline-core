"""Runtime settings — single source of truth for every tunable value.

Rule: no magic numbers, no hard-coded strings for paths/URLs/timeouts
anywhere in the code. They all route through this module.

Settings can be overridden by (in decreasing precedence):
    1. Explicit kwargs passed to `Settings(...)`
    2. Environment variables (PHLATLINE_*)
    3. `phlatline.yaml` in the working directory
    4. Hard-coded defaults below

Every default is a class-level attribute with a docstring explaining it.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl, PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


# --------------------------------------------------------------------------- #
# Execution limits
# --------------------------------------------------------------------------- #

class ExecutionSettings(BaseModel):
    """Knobs that govern how a single test run is executed."""

    request_timeout_s: PositiveFloat = Field(
        default=30.0,
        description="Per-HTTP-request timeout in seconds.",
    )
    verify_ssl: bool = Field(
        default=True,
        description="Whether to verify TLS certificates.",
    )
    follow_redirects: bool = Field(
        default=False,
        description="Whether to follow HTTP redirects. False so 3xx surfaces as a finding.",
    )


# --------------------------------------------------------------------------- #
# Test generation limits
# --------------------------------------------------------------------------- #

class GenerationSettings(BaseModel):
    """Knobs that govern how test cases are generated from a schema."""

    max_boundary_numeric_params: PositiveInt = Field(
        default=2,
        description="Max numeric params per op to stress-test at boundary values.",
    )
    max_boundary_string_params: PositiveInt = Field(
        default=1,
        description="Max string params per op to stress with long values.",
    )
    boundary_long_string_length: PositiveInt = Field(
        default=5000,
        description="Length of the stress-test 'long string' for string-param boundaries.",
    )
    boundary_numeric_max: int = Field(
        default=2_147_483_647,  # int32 max
        description="Upper-bound value used for numeric-param boundary tests.",
    )
    boundary_numeric_min: int = Field(
        default=-2_147_483_648,  # int32 min
        description="Lower-bound value used for numeric-param boundary tests.",
    )
    optional_query_param_probability: float = Field(
        default=0.8, ge=0.0, le=1.0,
        description="Probability of including a non-required query param in a generated request.",
    )
    max_response_preview_chars: PositiveInt = Field(
        default=2000,
        description="Truncate captured response bodies to this many characters in reports.",
    )


# --------------------------------------------------------------------------- #
# Fuzzing limits
# --------------------------------------------------------------------------- #

class FuzzSettings(BaseModel):
    """Knobs for the Schemathesis-backed fuzzer."""

    examples_per_operation: PositiveInt = Field(
        default=15,
        description="How many Hypothesis-generated examples to send per operation.",
    )
    max_fuzz_body_preview_chars: PositiveInt = Field(
        default=1500,
        description="Truncate fuzz response bodies captured in reports.",
    )


# --------------------------------------------------------------------------- #
# Reporting paths
# --------------------------------------------------------------------------- #

class ReportSettings(BaseModel):
    """Where reports are written."""

    output_dir: Path = Field(
        default=Path("./phlatline_results"),
        description="Base directory for all run output.",
    )
    html_report_filename: str = Field(
        default="report.html",
        description="Filename for the per-target HTML report.",
    )
    json_report_filename: str = Field(
        default="results.json",
        description="Filename for the per-target JSON report.",
    )
    project_index_filename: str = Field(
        default="index.html",
        description="Filename for the project-level summary page.",
    )
    combined_json_filename: str = Field(
        default="all_results.json",
        description="Filename for the project-level combined JSON.",
    )


# --------------------------------------------------------------------------- #
# Cloud agent (used by EE; config lives here so OSS knows the shape)
# --------------------------------------------------------------------------- #

class CloudSettings(BaseModel):
    """Config for the Phlatline Cloud upload agent. Consumed by phlatline-ee."""

    base_url: HttpUrl = Field(
        default=HttpUrl("https://api.phlatline.dev/"),
        description="Phlatline Cloud API base URL.",
    )
    upload_path: str = Field(
        default="/v1/runs",
        description="Path appended to base_url for run uploads.",
    )
    request_timeout_s: PositiveFloat = Field(
        default=15.0,
        description="Per-upload timeout.",
    )
    drain_timeout_s: PositiveFloat = Field(
        default=10.0,
        description="How long the CLI waits on pending uploads before exit.",
    )


# --------------------------------------------------------------------------- #
# Top-level settings — composes the sub-models
# --------------------------------------------------------------------------- #

class Settings(BaseSettings):
    """Top-level settings object. Access via `phlatline.config.settings`.

    Env-var overrides use the `PHLATLINE_` prefix and `__` for nesting, e.g.
        PHLATLINE_EXECUTION__REQUEST_TIMEOUT_S=60
        PHLATLINE_FUZZ__EXAMPLES_PER_OPERATION=25
    """

    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)
    generation: GenerationSettings = Field(default_factory=GenerationSettings)
    fuzz: FuzzSettings = Field(default_factory=FuzzSettings)
    report: ReportSettings = Field(default_factory=ReportSettings)
    cloud: CloudSettings = Field(default_factory=CloudSettings)

    model_config = SettingsConfigDict(
        env_prefix="PHLATLINE_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )


# Module-level singleton. Import `settings` anywhere that needs a tunable value.
settings = Settings()
