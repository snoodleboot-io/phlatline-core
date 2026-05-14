"""SDK abstract interfaces (Strategy pattern).

Every extension point Phlatline exposes is an ABC here. The OSS build ships
concrete defaults; the EE build plugs in richer implementations at import
time via the registry.

Interfaces defined:
    ResultSink       — receives CompletedRun (local report, cloud upload, etc.)
    AlertChannel     — delivers Alerts (Slack, PagerDuty, webhook)
    Scheduler        — drives recurring runs on a schedule (EE-only)
    TestExecutor     — executes a list of TestCases against a target
                       (OSS ships a sequential one; EE ships concurrent)

All interfaces support a drain() lifecycle so the CLI can flush async work
cleanly before exit.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Protocol

from phlatline.sdk.models import (
    Alert,
    CompletedRun,
    ScheduledJob,
    TargetSpec,
    TestCase,
    TestResult,
)


# --------------------------------------------------------------------------- #
# Drainable lifecycle — mixed into every interface that may do async work
# --------------------------------------------------------------------------- #

class Drainable(ABC):
    """Mixin for components that spawn background work.

    Core calls drain() before exit. Default no-op so pure-sync implementations
    don't have to override.
    """

    def drain(self, timeout_s: float = 10.0) -> None:
        """Wait up to timeout_s for pending async work to complete. No-op default."""
        return None


# --------------------------------------------------------------------------- #
# ResultSink — receives completed runs
# --------------------------------------------------------------------------- #

class ResultSink(Drainable):
    """Receives a CompletedRun. Implementations must not raise — they own
    their own error handling. Core never awaits the emit() return value."""

    name: str = "unnamed-sink"

    @abstractmethod
    def emit(self, run: CompletedRun) -> None:
        """Called once per completed target run. Must not block core for long."""


class NullResultSink(ResultSink):
    """Discards everything. Useful as a default when nothing else is registered."""

    name = "null"

    def emit(self, run: CompletedRun) -> None:
        return None


# --------------------------------------------------------------------------- #
# AlertChannel — delivers alerts
# --------------------------------------------------------------------------- #

class AlertChannel(Drainable):
    """Delivers an Alert somewhere (Slack, PagerDuty, email, webhook)."""

    name: str = "unnamed-channel"

    @abstractmethod
    def deliver(self, alert: Alert) -> None: ...


class NullAlertChannel(AlertChannel):
    """Drops alerts silently. OSS default."""

    name = "null"

    def deliver(self, alert: Alert) -> None:
        return None


# --------------------------------------------------------------------------- #
# Scheduler — drives recurring runs (EE-only feature)
# --------------------------------------------------------------------------- #

RunExecutor = Callable[[str], None]
"""Callback that runs a project by config path. Provided by core to Scheduler."""


class Scheduler(Drainable):
    """Manages recurring runs. OSS ships NullScheduler; EE replaces it."""

    name: str = "unnamed-scheduler"

    @abstractmethod
    def add(self, job: ScheduledJob) -> None: ...

    @abstractmethod
    def remove(self, job_id: str) -> None: ...

    @abstractmethod
    def list(self) -> list[ScheduledJob]: ...

    @abstractmethod
    def run_forever(self, run_executor: RunExecutor) -> None: ...


class NullScheduler(Scheduler):
    """OSS default — rejects all scheduling with a pointer to EE."""

    name = "null"
    _UPGRADE_MSG = (
        "Scheduling is a Phlatline Enterprise feature. "
        "Install phlatline-ee, or use an external cron that invokes `phlatline`."
    )

    def add(self, job: ScheduledJob) -> None:
        raise NotImplementedError(self._UPGRADE_MSG)

    def remove(self, job_id: str) -> None:
        raise NotImplementedError(self._UPGRADE_MSG)

    def list(self) -> list[ScheduledJob]:
        return []

    def run_forever(self, run_executor: RunExecutor) -> None:
        raise NotImplementedError(self._UPGRADE_MSG)


# --------------------------------------------------------------------------- #
# TestExecutor — executes test cases against a target
# --------------------------------------------------------------------------- #

class AuthContextLike(Protocol):
    """Structural type for what executors receive as auth material.

    Kept as a protocol (duck typing) so executors don't need to import the
    concrete auth implementation — helps keep the SDK decoupled from core.
    """

    headers: dict[str, str]
    query_params: dict[str, str]
    cookies: dict[str, str]


class TestExecutor(Drainable):
    """Executes a list of TestCases and returns TestResults.

    The OSS default is SequentialExecutor (one request at a time).
    The EE ConcurrentExecutor uses asyncio + httpx for parallelism.

    Implementations must be synchronous at the interface boundary — any
    async work lives inside execute() and is awaited before returning.
    """

    name: str = "unnamed-executor"

    @abstractmethod
    def execute(
        self,
        cases: list[TestCase],
        base_url: str,
        auth: AuthContextLike,
    ) -> list[TestResult]:
        """Execute all cases, return results in the same order as input.

        Must not raise for per-request failures — those become TestResult
        records with status=ERROR.
        """
