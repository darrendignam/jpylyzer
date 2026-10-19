#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fixtures that apply to every jpylyzer unit test."""

import signal

import pytest

from jpylyzer import config
from jpylyzer import jpylyzer

# Generous limit: the slowest tests (full corpus runs) take a few seconds
DEFAULT_TIMEOUT_SECONDS = 120


@pytest.fixture(autouse=True)
def fail_instead_of_hanging(request):
    """Turn a test that hangs (e.g. a parser that loops forever on malformed
    input) into a failure instead of stalling the whole run. Uses SIGALRM, so
    it has no effect on Windows."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    marker = request.node.get_closest_marker("timeout")
    seconds = marker.args[0] if marker else DEFAULT_TIMEOUT_SECONDS

    def timeout(signum, frame):
        raise TimeoutError(f"test did not finish within {seconds} s")

    previous = signal.signal(signal.SIGALRM, timeout)
    signal.alarm(seconds)
    yield
    signal.alarm(0)
    signal.signal(signal.SIGALRM, previous)


@pytest.fixture(autouse=True)
def isolate_global_state():
    """Restore jpylyzer's module-level settings after each test, so tests do
    not depend on the order they run in."""
    settings = {name: getattr(config, name) for name in dir(config) if name.isupper()}
    yield
    for name, value in settings.items():
        setattr(config, name, value)
    jpylyzer.EXISTING_FILES.clear()
