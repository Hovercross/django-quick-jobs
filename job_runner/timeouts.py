from datetime import timedelta
from threading import Thread, Event, Lock
from typing import Callable, Dict, Optional, Set, Tuple
import time

from structlog import get_logger

logger = get_logger()

Callback = Callable[[], None]


class TimeoutTracker(Thread):
    def __init__(self, stop: Event):
        self._check_timeout_evt = Event()
        self._stop_evt = stop
        self._lock = Lock()
        self._running: Dict[object, Tuple[float, Callback]] = {}
        self._log = logger.bind(process="timeout tracker")

        super().__init__(name="Timeout tracker")

    def _watch_for_stop(self):
        self._stop_evt.wait()

        self._check_timeout_evt.set()

    def add_timeout(self, duration: timedelta, callback: Callback) -> Callback:
        """Add a timeout to the callbacks"""

        key = object()

        def cancel():
            with self._lock:
                if not key in self._running:
                    self._log.warning("Got timeout cancelation after timeout fired")
                    return

                del self._running[key]

        timeout_time = time.monotonic() + duration.total_seconds()

        with self._lock:
            self._check_timeout_evt.set()

            # Set the event so the loop fires,
            # which will update the sleep time in case this is to be the next firing event
            self._running[key] = (timeout_time, callback)

        return cancel

    def run(self):
        """Loop through until a timeout is reached"""

        # Start up a background thread that watches for a stop event
        Thread(name="Timeout tracker stop watcher", target=self._watch_for_stop).start()

        while not self._stop_evt.is_set():
            self._log.debug("Running timeout tracker checks")
            delay = self._run_once()
            self._log.debug("Timeout tracker checks finished", next_run_delay=delay)
            self._check_timeout_evt.wait(delay)

    def _run_once(self) -> Optional[float]:
        """Fire all timeouts and return the delay for the next execution"""

        with self._lock:
            self._check_timeout_evt.clear()
            self._fire_timeouts()
            return self._next_timeout_delay

    def _fire_timeouts(self):
        """Loop through all the running timeouts and fire appropriate ones"""

        to_remove: Set[object] = set()

        for key, (timeout, callback) in self._running.items():
            if timeout < time.monotonic():
                self._log.debug("Timeout reached")
                to_remove.add(key)
                callback()

        for key in to_remove:
            del self._running[key]

    @property
    def _next_timeout(self) -> Optional[float]:
        """The monotonic timeout of the nearest timeout object"""

        timeouts = [timeout for timeout, _ in self._running.values()]

        if not timeouts:
            return None

        return min(timeouts)

    @property
    def _next_timeout_delay(self) -> Optional[float]:
        if not self._next_timeout:
            return None

        return self._next_timeout - time.monotonic()
