"""Detailed tests for timeout functionality"""

from threading import Event
from datetime import timedelta
import time

import pytest

from .timeouts import TimeoutTracker


def test_exit():
    stop_event = Event()
    tracker = TimeoutTracker(stop_event)
    tracker.daemon = True
    tracker.start()

    stop_event.set()
    tracker.join(1)
    assert not tracker.is_alive()


def test_basic_cancel():
    stop_event = Event()
    tracker = TimeoutTracker(stop_event)
    tracker.daemon = True
    tracker.start()

    got_cancel = Event()

    cancel = tracker.add_timeout(timedelta(seconds=1), got_cancel.set)
    cancel()

    time.sleep(2)
    assert not got_cancel.is_set()
    stop_event.set()
    tracker.join()


def test_basic_timeout():
    stop_event = Event()
    tracker = TimeoutTracker(stop_event)
    tracker.daemon = True
    tracker.start()

    got_cancel = Event()
    tracker.add_timeout(timedelta(seconds=1), got_cancel.set)

    time.sleep(2)
    assert got_cancel.is_set()
    stop_event.set()  # Don't leave the thread hanging
    tracker.join()  # Make sure it exited


def test_multiple_timeouts():
    stop_event = Event()
    tracker = TimeoutTracker(stop_event)
    tracker.daemon = True
    tracker.start()

    t_1 = Event()
    t_2 = Event()

    tracker.add_timeout(timedelta(seconds=1), t_1.set)
    tracker.add_timeout(timedelta(seconds=10), t_2.set)

    assert not t_1.is_set()
    assert not t_2.is_set()

    time.sleep(2)
    assert t_1.is_set()
    assert not t_2.is_set()

    stop_event.set()  # Don't leave the thread hanging
    tracker.join()  # Make sure it exited
