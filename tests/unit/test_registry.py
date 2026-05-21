"""Unit tests for phlatline.sdk.registry."""
from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from phlatline.core.sequential_executor import SequentialExecutor
from phlatline.sdk.interfaces import NullResultSink, NullScheduler
from phlatline.sdk.registry import (
    clear_registry,
    get_alert_channels,
    get_executor,
    get_result_sinks,
    get_scheduler,
    register_alert_channel,
    register_executor,
    register_result_sink,
    register_scheduler,
)


@pytest.fixture(autouse=True)
def _reset_registry():
    """Clear the registry before each test to prevent state bleed."""
    clear_registry()
    yield
    clear_registry()


# --------------------------------------------------------------------------- #
# Result sinks
# --------------------------------------------------------------------------- #

class TestSuiteResultSinks:
    def test_no_registration_returns_null_sink(self):
        sinks = get_result_sinks()
        assert len(sinks) == 1
        assert isinstance(sinks[0], NullResultSink)

    def test_register_one_sink_replaces_null(self):
        mock_sink = MagicMock()
        mock_sink.name = "mock-sink"
        register_result_sink(mock_sink)
        sinks = get_result_sinks()
        assert sinks == [mock_sink]
        assert not any(isinstance(s, NullResultSink) for s in sinks)

    def test_register_two_sinks_returns_both(self):
        sink_a = MagicMock()
        sink_a.name = "sink-a"
        sink_b = MagicMock()
        sink_b.name = "sink-b"
        register_result_sink(sink_a)
        register_result_sink(sink_b)
        sinks = get_result_sinks()
        assert sink_a in sinks
        assert sink_b in sinks
        assert len(sinks) == 2

    def test_get_result_sinks_returns_copy(self):
        mock_sink = MagicMock()
        mock_sink.name = "mock-sink"
        register_result_sink(mock_sink)
        copy_a = get_result_sinks()
        copy_a.append(MagicMock())
        copy_b = get_result_sinks()
        assert len(copy_b) == 1  # mutation of copy_a did not affect the registry


# --------------------------------------------------------------------------- #
# Alert channels
# --------------------------------------------------------------------------- #

class TestSuiteAlertChannels:
    def test_no_registration_returns_empty_list(self):
        channels = get_alert_channels()
        assert channels == []

    def test_register_channel_appears_in_list(self):
        ch = MagicMock()
        ch.name = "mock-channel"
        register_alert_channel(ch)
        channels = get_alert_channels()
        assert ch in channels


# --------------------------------------------------------------------------- #
# Scheduler
# --------------------------------------------------------------------------- #

class TestSuiteScheduler:
    def test_no_registration_returns_null_scheduler(self):
        sched = get_scheduler()
        assert isinstance(sched, NullScheduler)

    def test_register_scheduler_overrides_null(self):
        mock_sched = MagicMock()
        mock_sched.name = "mock-scheduler"
        register_scheduler(mock_sched)
        assert get_scheduler() is mock_sched

    def test_second_registration_overrides_first(self):
        first = MagicMock()
        first.name = "first-scheduler"
        second = MagicMock()
        second.name = "second-scheduler"
        register_scheduler(first)
        register_scheduler(second)
        assert get_scheduler() is second


# --------------------------------------------------------------------------- #
# Executor
# --------------------------------------------------------------------------- #

class TestSuiteExecutor:
    def test_no_registration_returns_sequential_executor(self):
        executor = get_executor()
        assert isinstance(executor, SequentialExecutor)

    def test_register_executor_overrides_default(self):
        mock_exec = MagicMock()
        mock_exec.name = "mock-executor"
        register_executor(mock_exec)
        assert get_executor() is mock_exec

    def test_second_registration_overrides_first(self):
        first = MagicMock()
        first.name = "first-executor"
        second = MagicMock()
        second.name = "second-executor"
        register_executor(first)
        register_executor(second)
        assert get_executor() is second


# --------------------------------------------------------------------------- #
# clear_registry
# --------------------------------------------------------------------------- #

class TestSuiteClearRegistry:
    def test_clear_resets_all_to_defaults(self):
        sink = MagicMock()
        sink.name = "s"
        ch = MagicMock()
        ch.name = "c"
        sched = MagicMock()
        sched.name = "sc"
        executor = MagicMock()
        executor.name = "ex"

        register_result_sink(sink)
        register_alert_channel(ch)
        register_scheduler(sched)
        register_executor(executor)

        clear_registry()

        assert isinstance(get_result_sinks()[0], NullResultSink)
        assert get_alert_channels() == []
        assert isinstance(get_scheduler(), NullScheduler)
        assert isinstance(get_executor(), SequentialExecutor)


# --------------------------------------------------------------------------- #
# Thread safety smoke test
# --------------------------------------------------------------------------- #

class TestSuiteThreadSafety:
    def test_concurrent_registrations(self):
        sinks = []
        for i in range(10):
            m = MagicMock()
            m.name = f"sink-{i}"
            sinks.append(m)

        threads = [
            threading.Thread(target=register_result_sink, args=(sink,))
            for sink in sinks
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        registered = get_result_sinks()
        assert len(registered) == 10
        for sink in sinks:
            assert sink in registered
