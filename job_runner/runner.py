"""The coordinator is responsible for running all jobs"""

from random import random
from threading import Thread, Event
import time
from typing import List, Optional

import django.db

from job_runner.environment import get_environments
from job_runner.registration import RegisteredJob

from structlog import get_logger

logger = get_logger(__name__)


class JobThread(Thread):
    """Runs a single job on a single schedule"""

    def __init__(self, job: RegisteredJob, stop_event: Event):
        self.job = job
        self.stopping = stop_event
        self.log = logger.bind(job_name=self.job.name)

        self._next_run = job.variance.total_seconds() * random()
        self._next_database_cleanup: Optional[float] = None

        super().__init__()

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

        # Add a little pad to account for clock weirdness, since Django uses time.monotonic to
        # track when it needs to clean up
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

        try:
            django.db.reset_queries()  # This is normally run before each request
            self.job(run_env)
            self.log.info("Job finished successfully")
        except Exception as exc:
            self.log.exception("Finished job with exception", error=str(exc))

        # The default is to obey the job mechanics
        self._next_run = (
            time.monotonic()
            + self.job.interval.total_seconds()
            - started_at
            + self.job.variance.total_seconds() * random()
        )

        if tracker_env.requested_rerun:
            # Override next run to go immediately if the job requests it
            self.log.debug("Job requested rerun without delay")
            self._next_run = time.monotonic()

        if tracker_env.requested_stop:
            self.log.warning("Job requested stop")
            self.stopping.set()

        self._cleanup_database()
        self._schedule_next_db_cleanup()
        self.log.info(
            "Job execution finished successfully",
            next_run=self._next_run,
            now=time.monotonic(),
        )

    def run(self):
        self.log.info(
            "Starting job execution thread",
            interval=self.job.interval,
            variance=self.job.variance,
        )

        while not self.stopping.is_set():
            delay = self._next_event_delay
            self.log.debug("Delaying thread loop", delay=delay)
            self.stopping.wait(delay)

            if self.stopping.is_set():
                return

            self._conditional_run()
            self._conditional_cleanup()

        self.log.info("Job thread stopped")
