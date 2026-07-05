"""Shared pytest fixtures for phlatline-core.

S0.1 scaffolding — holds only what the sample scenarios need.
Real fixtures (loaded schemas, demo server, executor instances,
TestCase/TestResult factories) arrive with S1.1.1.
"""
from __future__ import annotations

import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner() -> CliRunner:
    """Isolated CliRunner for invoking Click commands in-process."""
    return CliRunner()
