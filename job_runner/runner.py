"""The coordinator is responsible for running all jobs"""

from datetime import datetime, timedelta

from random import random
from threading import Thread, Event
from typing import Optional

from django.utils import timezone
import django.db

from job_runner.environment import TrackerEnv, get_environments
from job_runner.registration import RegisteredJob
from job_runner.time import AutoTime, read_auto_time

from structlog import get_logger

logger = get_logger(__name__)


class JobThread(Thread):
    """Runs a single job on a single schedule"""

    def __init__(self, job: RegisteredJob, stop_event: Event):
        self.job = job
        self.stopping = stop_event
        self.log = logger.bind(job_name=self.job.name)

        self._next_run = _random_time(0, job.variance)
        self._next_cleanup = _random_time(30, 5)

        super().__init__()

    def _cleanup(self):
        django.db.close_old_connections()

    def _conditional_cleanup(self):
        self.log.debug("Beginning conditional cleanup")
        if timezone.now() < self._next_cleanup:
            self.log.debug("Cleanup not ready")
            return

        self.log.info("Running cleanup")

        self._cleanup()
        self._next_cleanup = _random_time(1, 0)

    def _conditional_run(self):
        self.log.debug("Beginning conditional run")
        if timezone.now() < self._next_run:
            self.log.debug("Not ready to run")
            return

        self.log.info("Beginning job execution")

        started_at = timezone.now()
        env = self._run_once()

        # The default
        self._next_run = _random_time(self.job.interval, self.job.variance, started_at)

        if env.requested_rerun:
            # Override next run to go now
            self.log.debug("Job requested rerun without delay")
            self._next_run = timezone.now()

        self.log.info("Job execution finished successfully", next_run=self._next_run)

    @property
    def _next_event(self) -> datetime:
        """Figure out the next time anything happens"""

        return min(self._next_cleanup, self._next_run)

    @property
    def _next_event_delay(self) -> timedelta:
        return max(self._next_event - timezone.now(), timedelta(0))

    def _run_once(self) -> TrackerEnv:
        self.log.info("Job starting")

        run_env, tracker_env = get_environments(self.stopping)

        try:
            self.job(run_env)
            self.log.info("Job finished successfully")
        except Exception as exc:
            self.log.exception("Finished job with exception", error=str(exc))

        return tracker_env

    def run(self):
        self.log.info(
            "Starting job execution thread",
            interval=self.job.interval,
            variance=self.job.variance,
        )

        while not self.stopping.is_set():
            delay = self._next_event_delay
            self.log.debug("Delaying thread loop", delay=delay.total_seconds())
            self.stopping.wait(delay.total_seconds())

            self._conditional_run()
            self._conditional_cleanup()

        self.log.info("Job thread stopped")


def _random_time(
    fixed: AutoTime, variance: AutoTime, base: Optional[datetime] = None
) -> datetime:
    _fixed = read_auto_time(fixed) or timedelta(0)
    _variance = read_auto_time(variance) or timedelta(0)
    _base = base and base or timezone.now()

    return _base + _fixed + _variance * random()
