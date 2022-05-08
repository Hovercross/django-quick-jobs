"""Detailed tests for timeout functionality"""

from threading import Event
from datetime import timedelta
import time

import pytest

from .timeouts import TimeoutTracker


@pytest.mark.timeout(30)
def test_exit():
    stop_event = Event()
    tracker = TimeoutTracker(stop_event)
    tracker.start()

    stop_event.set()
    tracker.join(1)
    assert not tracker.is_alive()


@pytest.mark.timeout(30)
def test_basic_cancel():
    stop_event = Event()
    tracker = TimeoutTracker(stop_event)
    tracker.start()

    cancel = tracker.add_timeout("test", timedelta(seconds=1))
    cancel()

    time.sleep(2)
    assert not stop_event.is_set()
    stop_event.set()


@pytest.mark.timeout(30)
def test_basic_timeout():
    stop_event = Event()
    tracker = TimeoutTracker(stop_event)
    tracker.start()

    cancel = tracker.add_timeout("test", timedelta(seconds=1))
    time.sleep(2)
    assert stop_event.is_set()
    stop_event.set()  # Backup in case the tracker didn't fire it itself
