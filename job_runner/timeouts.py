from dataclasses import dataclass
from datetime import timedelta
from threading import Thread, Event, Lock
from typing import Callable, Dict, Optional
import time

from structlog import get_logger, BoundLogger

logger: BoundLogger = get_logger()

SimpleCallback = Callable[[], None]


@dataclass
class _TimeoutTracker:
    key: object
    timeout: float
    name: str


class TimeoutTracker(Thread):
    def __init__(self, stop: Event):
        self._check_timeout_evt = Event()
        self._stop_evt = stop
        self._lock = Lock()
        self._running: Dict[object, _TimeoutTracker] = {}
        self._log = logger.bind(process="timeout tracker")

        super().__init__(name="timeout watcher")

    def _watch_for_stop(self):
        self._stop_evt.wait()

        self._check_timeout_evt.set()

    def add_timeout(self, name: str, duration: timedelta) -> SimpleCallback:
        """Add a timeout to the callbacks"""

        key = object()

        def cancel():
            with self._lock:
                del self._running[key]

        timeout_time = time.monotonic() + duration.total_seconds()
        tracked = _TimeoutTracker(key=key, timeout=timeout_time, name=name)

        with self._lock:
            self._check_timeout_evt.set()

            # Set the event so the loop fires,
            # which will update the sleep time in case this is to be the next firing event
            self._running[key] = tracked

        return cancel

    def run(self):
        """Loop through until a timeout is reached"""

        # Start up a background thread that watches for a stop event
        Thread(name="timeout stop watcher", target=self._watch_for_stop).start()

        while not self._stop_evt.is_set():
            delay = self._run_once()
            self._check_timeout_evt.wait(delay)

    def _run_once(self) -> Optional[float]:
        """Fire all timeouts and return the delay for the next execution"""

        with self._lock:
            self._check_timeout_evt.clear()
            self._fire_timeouts()
            return self._next_timeout_delay

    def _fire_timeouts(self):
        """Loop through all the running timeouts and fire appropriate ones"""

        got_timeout = False

        for timeout in self._running.values():
            if timeout.timeout < time.monotonic():
                self._log.warn("Timeout reached", name=timeout.name)
                got_timeout = True

        if got_timeout:
            self._stop_evt.set()

    @property
    def _next_timeout(self) -> Optional[float]:
        """The monotonic timeout of the nearest timeout object"""

        timeouts = [obj.timeout for obj in self._running.values()]

        if not timeouts:
            return None

        return min(timeouts)

    @property
    def _next_timeout_delay(self) -> Optional[float]:
        if not self._next_timeout:
            return None

        return time.monotonic() - self._next_timeout
