"""The coordinator is responsible for running all jobs"""

from datetime import timedelta
from typing import List

from random import random
from threading import Thread, Event, Lock

from django.utils import timezone

from structlog import get_logger
from job_runner.environment import TrackerEnv, get_environments

from job_runner.tracker import RegisteredJob

logger = get_logger(__name__)


class JobThread(Thread):
    """Runs a single job on a single schedule"""

    def __init__(self, job: RegisteredJob, stop_event: Event):
        self.job = job
        self.stopping = stop_event
        self.log = logger.bind(job_name=self.job.name)

        super().__init__()

    def _initial_wait(self):
        wait_for = (self.job.variance * random()).total_seconds()

        if not wait_for:
            self.log.debug("Not performing initial wait")
            return

        self.log.info("Delaying job first run", wait_time=wait_for)
        self.stopping.wait(wait_for)

    def _run_once(self) -> TrackerEnv:
        self.log.info("Job starting")

        run_env, tracker_env = get_environments(self.stopping)

        try:
            self.job.func(run_env)
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

        self._initial_wait()

        while not self.stopping.is_set():
            started_at = timezone.now()
            tracker_env = self._run_once()

            if tracker_env.requested_rerun:
                self.log.debug("Job requested rerun without delay")
                continue

            this_interval = self.job.interval + random() * self.job.variance
            next_run = started_at + this_interval
            now = timezone.now()
            delay = max(next_run - now, timedelta())
            delay_seconds = delay.total_seconds()

            if delay:
                self.log.debug("Delaying next job execution", delay=delay_seconds)

            self.stopping.wait(delay_seconds)

        self.log.info("Job thread stopped")

    def request_stop(self):
        self.stopping.set()
