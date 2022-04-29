"""The coordinator is responsible for running all jobs"""

from datetime import timedelta
from typing import List

from random import random
from threading import Thread, Event, Lock

from django.utils import timezone

from structlog import get_logger
from job_runner.environment import TrackerEnv

from job_runner.tracker import RegisteredJob, RunEnvironment

logger = get_logger(__name__)


class _JobThread(Thread):
    """Runs a single job on a single schedule"""

    def __init__(self, job: RegisteredJob):
        self.job = job
        self.stopping = Event()
        self.log = logger.bind(job_name=self.job.name)

        super().__init__()

    def run(self):
        self.log.info(
            "Starting job execution thread",
            interval=self.job.interval,
            variance=self.job.variance,
        )

        # Use the variance as an initial delay to prevent thundering herd
        initial_delay = self.job.variance * random()

        if initial_delay:
            self.log.info(
                "Waiting for first job run", wait_time=initial_delay.total_seconds()
            )

            # If we get interrupted during the initial wait,
            # we'll immediately return and then exit at the
            # start of the while loop below
            self.stopping.wait(initial_delay.total_seconds())

        while not self.stopping.is_set():
            self.log.info("Job starting")
            started_at = timezone.now()

            env = TrackerEnv(self.stopping)

            try:
                self.job.func(env.run_environment)

                self.log.info("Job finished successfully")

            except Exception as exc:
                self.log.exception("Finished job with exception", error=str(exc))

            if env.did_request_rerun:
                self.log.debug("Job requested rerun without delay")

            delay = timedelta(seconds=0)
            if not env.did_request_rerun:
                this_interval = self.job.interval + random() * self.job.variance
                next_run = started_at + this_interval
                now = timezone.now()
                delay = next_run - now

            if delay.total_seconds() > 0:
                self.log.debug(
                    "Job not ready to be run", wait_time=delay.total_seconds()
                )

                # We do the delay inside of the event wait so that we can respond
                # immediately to a stop signal. If we get a stop signal, we'll
                # stop the wait here and then immediately exit the while loop
                self.stopping.wait(delay.total_seconds())
            else:
                self.log.debug("Job is being executed with no delay")

        self.log.info("Job thread stopped")

    def request_stop(self):
        self.stopping.set()


class Coordinator(Thread):
    def __init__(self):
        self._evt = Event()
        self._workers: List[_JobThread] = []
        self._lock = Lock()
        self.log = logger.bind(thread="coordinator")

        super().__init__()

    def run(self):
        self.log.info("Thread started")
        self._evt.wait()
        self.log.info("Thread beginning shutdown")

        for worker in self._workers:
            self.log.debug("Signaling worker stop", job_name=worker.job.name)
            worker.request_stop()

        for worker in self._workers:
            self.log.info("Waiting for worker shutdown", job_name=worker.job.name)
            worker.join()
            self.log.info("Worker shutdown finished", job_name=worker.job.name)

        self.log.info("Job tracker thread finished")
        self._evt.clear()

    def add(self, job: RegisteredJob):
        """Add a job to the list of running jobs"""

        with self._lock:
            thread = _JobThread(job)
            self._workers.append(thread)
            thread.start()

    def request_stop(self):
        self.log.info("Coordinator stop request received")
        self._evt.set()
