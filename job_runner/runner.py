"""The coordinator is responsible for running all jobs"""

from random import random
from threading import Thread, Event
import time
from typing import Callable, List, Optional

import django.db

from job_runner.environment import get_environments, SleepInterrupted
from job_runner.registration import RegisteredJob
from job_runner.timeouts import TimeoutTracker

from structlog import get_logger

logger = get_logger(__name__)


class JobThread(Thread):
    """Runs a single job on a single schedule"""

    def __init__(
        self,
        job: RegisteredJob,
        stop: Event,
        throw_error: Callable[[], None],
        timeout_tracker: TimeoutTracker,
    ):
        self.job = job
        self.stopping = stop
        self._on_fatal = throw_error
        self.log = logger.bind(job_name=self.job.name)

        self._next_run = job.variance.total_seconds() * random()
        self._next_database_cleanup: Optional[float] = None
        self._timeout_tracker = timeout_tracker

        super().__init__()

        self.name = f"Runner: {self.job.name}"

    @property
    def _next_event(self) -> float:
        """Figure out the next time anything happens"""

        if self._next_database_cleanup:
            return min(self._next_database_cleanup, self._next_run)

        return self._next_run

    @property
    def _next_event_delay(self) -> float:
        return max(self._next_event - time.monotonic(), 0)

    def _conditional_cleanup(self):
        self.log.debug("Beginning conditional cleanup")

        if not self._next_database_cleanup:
            self.log.debug("Cleanup not scheduled")
            return

        if time.monotonic() < self._next_database_cleanup:
            self.log.debug("Cleanup not ready")
            return

        self._cleanup_database()

    def _conditional_run(self):
        self.log.debug("Beginning conditional run")
        if time.monotonic() < self._next_run:
            self.log.debug("Not ready to run")
            return

        self._run_once()

    def _cleanup_database(self):
        self.log.info("Running cleanup")

        # Near as I can tell, the connection handler is thread local,
        # so this does need to be run for every different job
        django.db.close_old_connections()
        self._next_database_cleanup = None

    def _schedule_next_db_cleanup(self):
        delays: List[int] = []

        for conn_name in django.db.connections:
            conn = django.db.connections[conn_name]
            max_age = conn.settings_dict["CONN_MAX_AGE"]
            if not max_age:
                continue

            delays.append(max_age)

        if not delays:
            return

        delay = min(delays)
        self._next_database_cleanup = time.monotonic() + delay
        self.log.debug(
            "Scheduling database cleanup",
            next_run=self._next_database_cleanup,
            now=time.monotonic(),
        )

    def _run_once(self):
        self.log.info("Job starting")

        run_env, tracker_env = get_environments(self.stopping)
        started_at = time.monotonic()
        timeout_fired = Event()

        def fire_timeout():
            self.log.error(
                "Job timed out",
                start_time=started_at,
                timeout=self.job.timeout.total_seconds(),
            )
            timeout_fired.set()
            self.stopping.set()

        cancel_func: Optional[Callable[[], None]] = None

        if self.job.timeout:
            cancel_func = self._timeout_tracker.add_timeout(
                self.job.timeout, fire_timeout
            )

        try:
            django.db.reset_queries()  # This is normally run before each request
            self.job(run_env)
            self.log.info("Job finished successfully")
        except SleepInterrupted:
            self.log.info("Job was interrupted during sleep")
        except Exception as exc:
            if tracker_env.requested_fatal_errors:
                self.log.warning("Job requested fatal errors, propagating error")
                raise exc
            self.log.exception("Finished job with exception", error=str(exc))
        finally:
            if cancel_func:
                cancel_func()

        if timeout_fired.is_set():
            self.log.debug(
                "Edge case race condition detected: "
                "job timeout fired out and also finished"
            )

            # Set on fatal because this is ultimately a bad thing and
            # we don't want a clean exit if we are exiting due to timeout
            self._on_fatal()

        now = time.monotonic()
        execution_time = now - started_at

        interval = self.job.interval.total_seconds()
        variance = self.job.variance.total_seconds() * random()
        # The default is to obey the job mechanics
        self._next_run = now + interval + variance - execution_time

        if tracker_env.requested_rerun:
            # Override next run to go immediately if the job requests it
            self.log.debug("Job requested rerun without delay")
            self._next_run = now

        if tracker_env.requested_stop:
            self.log.warning("Job requested stop")
            self.stopping.set()

        self._cleanup_database()
        self._schedule_next_db_cleanup()
        self.log.info(
            "Job execution finished",
            next_run=self._next_run,
            execution_time=execution_time,
            now=now,
        )

    def _run(self):
        self.log.info(
            "Starting job execution thread",
            interval=self.job.interval,
            variance=self.job.variance,
        )

        while not self.stopping.is_set():
            delay = self._next_event_delay
            self.log.debug("Delaying thread loop", delay=delay)
            if self.stopping.wait(delay):
                return

            self._conditional_run()
            self._conditional_cleanup()

        self.log.info("Job thread stopped")

    def run(self):
        try:
            self._run()
        except Exception as exc:
            # All exceptions from jobs should be caught in the job run method.
            # An exception here indicates that something went wrong with
            # the runner itself and is not anticipated to be recoverable.
            self.log.exception("Error thrown in job thread", error=str(exc))
            self._on_fatal()
