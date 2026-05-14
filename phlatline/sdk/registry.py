"""Registry — singleton composition root for SDK extensions.

Pattern: Registry + Strategy + Composition Root.

Extensions self-register at import time via the module-level register_*()
helpers. Core asks the registry for components via the get_*() helpers;
the registry returns either registered extensions or a safe default.

Singleton mechanics use a module-level instance (Pythonic, avoids thread
issues) rather than a metaclass dance.
"""
from __future__ import annotations

from threading import RLock

from phlatline.sdk.interfaces import (
    AlertChannel,
    NullAlertChannel,
    NullResultSink,
    NullScheduler,
    ResultSink,
    Scheduler,
    TestExecutor,
)


class _Registry:
    """Holds the set of active extension instances.

    Rules:
        * Sinks and alert channels: many can register; all receive each event.
        * Scheduler and executor: one winner; later registrations override.
        * Getters return safe defaults when no extension has registered.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._sinks: list[ResultSink] = []
        self._channels: list[AlertChannel] = []
        self._scheduler: Scheduler | None = None
        self._executor: TestExecutor | None = None

    # --- sinks -------------------------------------------------------------

    def register_result_sink(self, sink: ResultSink) -> None:
        with self._lock:
            self._sinks.append(sink)

    def get_result_sinks(self) -> list[ResultSink]:
        with self._lock:
            return list(self._sinks) if self._sinks else [NullResultSink()]

    # --- alert channels ----------------------------------------------------

    def register_alert_channel(self, channel: AlertChannel) -> None:
        with self._lock:
            self._channels.append(channel)

    def get_alert_channels(self) -> list[AlertChannel]:
        with self._lock:
            return list(self._channels)

    # --- scheduler (one winner) --------------------------------------------

    def register_scheduler(self, scheduler: Scheduler) -> None:
        with self._lock:
            self._scheduler = scheduler

    def get_scheduler(self) -> Scheduler:
        with self._lock:
            return self._scheduler if self._scheduler is not None else NullScheduler()

    # --- executor (one winner) ---------------------------------------------

    def register_executor(self, executor: TestExecutor) -> None:
        with self._lock:
            self._executor = executor

    def get_executor(self) -> TestExecutor:
        with self._lock:
            if self._executor is not None:
                return self._executor
            # Lazy default so importing the registry doesn't force loading core
            from phlatline.core.sequential_executor import SequentialExecutor
            return SequentialExecutor()

    # --- test hooks --------------------------------------------------------

    def clear(self) -> None:
        """Reset all registrations. For tests only."""
        with self._lock:
            self._sinks.clear()
            self._channels.clear()
            self._scheduler = None
            self._executor = None


# Module-level singleton
_REGISTRY = _Registry()


# --- public functional API ---------------------------------------------------

def register_result_sink(sink: ResultSink) -> None:
    _REGISTRY.register_result_sink(sink)


def register_alert_channel(channel: AlertChannel) -> None:
    _REGISTRY.register_alert_channel(channel)


def register_scheduler(scheduler: Scheduler) -> None:
    _REGISTRY.register_scheduler(scheduler)


def register_executor(executor: TestExecutor) -> None:
    _REGISTRY.register_executor(executor)


def get_result_sinks() -> list[ResultSink]:
    return _REGISTRY.get_result_sinks()


def get_alert_channels() -> list[AlertChannel]:
    return _REGISTRY.get_alert_channels()


def get_scheduler() -> Scheduler:
    return _REGISTRY.get_scheduler()


def get_executor() -> TestExecutor:
    return _REGISTRY.get_executor()


def clear_registry() -> None:
    """Reset all registrations. For tests only."""
    _REGISTRY.clear()
