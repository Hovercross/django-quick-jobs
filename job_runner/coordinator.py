"""The coordinator is responsible for running all jobs"""

from typing import Callable, List

from datetime import datetime
from random import random
from threading import Thread, Event, Lock

from structlog import get_logger

from job_runner.tracker import RegisteredJob
from job_runner.exceptions import RequestRestart

logger = get_logger()


class _JobThread(Thread):
    """Runs a single job on a single schedule"""

    def __init__(self, job: RegisteredJob, request_restart: Callable[[], None]):
        self.job = job
        self.stopping = Event()
        self.log = logger.bind(job_name=self.job.name)
        self.request_restart = request_restart

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
            started_at = datetime.now()

            try:
                run_again = self.job.func()
                self.log.info("Finished successfully")

                if run_again:
                    self.log.info(
                        "Immediately rescheduling job",
                    )
                    continue

            except RequestRestart as exc:
                self.log.exception("Job requested restart", error=str(exc))
                self.request_restart()
            except Exception as exc:
                self.log.exception("Finished job with exception", error=str(exc))

            this_interval = self.job.interval + random() * self.job.variance
            next_run = started_at + this_interval
            now = datetime.now()
            delay = next_run - now

            if delay.total_seconds() > 0:
                self.log.info(
                    "Job not ready to be run", wait_time=delay.total_seconds()
                )

                # We do the delay inside of the event wait so that we can respond
                # immediately to a stop signal. If we get a stop signal, we'll
                # stop the wait here and then immediately exit the while loop
                self.stopping.wait(delay.total_seconds())
            else:
                self.log.info("Job is being executed with no delay")

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
            thread = _JobThread(job, self.request_stop)
            self._workers.append(thread)
            thread.start()

    def request_stop(self):
        self.log.info("Signaling coordinator stop")
        self._evt.set()
