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
        self._running: Dict[int, Tuple[float, Callback]] = {}
        self._log = logger.bind(process="timeout tracker")
        self._key = 0

        super().__init__(name="Timeout tracker")

    def add_timeout(self, duration: timedelta, callback: Callback) -> Callback:
        """Add a timeout to the callbacks"""

        with self._lock:
            key = self._key
            self._key += 1

            cancel = self._get_cancel(key)
            timeout_time = time.monotonic() + duration.total_seconds()
            self._running[key] = (timeout_time, callback)

            # Set the event so the loop fires,
            # which will update the sleep time in case this is to be the next firing event
            self._check_timeout_evt.set()

        return cancel

    def run(self):
        """Loop through until a timeout is reached"""

        # Start up a background thread that watches for a stop event
        stop_watcher = Thread(target=self._watch_for_stop)
        stop_watcher.name = "Timeout tracker stop watcher"
        stop_watcher.daemon = True
        stop_watcher.start()

        while True:
            self._log.debug("Running timeout tracker checks")

            with self._lock:
                self._log.debug("Lock acquired for timeout tracker checks")
                self._check_timeout_evt.clear()
                self._fire_timeouts()
                delay = self._timeout_delay
                if self._stop_evt.is_set():
                    break

            self._check_timeout_evt.wait(delay)

        self._log.debug("Waiting for stop watcher to close")
        stop_watcher.join()
        self._log.info("Timeout watcher exiting")

    def _watch_for_stop(self):
        self._log.debug("Beginning stop watcher")
        self._stop_evt.wait()
        self._log.debug("Stop event fired, setting check timeout event")

        with self._lock:
            self._check_timeout_evt.set()

        self._log.debug("Stop watcher finished")

    def _get_cancel(self, key: int) -> Callback:
        """Get a cancellation function for a given key"""

        def cancel():
            with self._lock:
                if not key in self._running:
                    self._log.warning("Got timeout cancellation after timeout fired")
                    return

                del self._running[key]

        return cancel

    def _fire_timeouts(self):
        """Loop through all the running timeouts and fire appropriate ones"""

        to_remove: Set[int] = set()

        for key, (timeout, callback) in self._running.items():
            if timeout < time.monotonic():
                self._log.debug("Timeout reached")
                to_remove.add(key)
                callback()

        for key in to_remove:
            del self._running[key]

    @property
    def _timeout_delay(self) -> Optional[float]:
        """Figure out how long to delay until the next event"""

        next_timeout: Optional[float] = None

        for timeout, _ in self._running.values():
            if not next_timeout:
                next_timeout = timeout
                continue

            if timeout < next_timeout:
                next_timeout = timeout

        if next_timeout:
            return next_timeout - time.monotonic()

        return None
