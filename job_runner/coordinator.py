"""The coordinator is responsible for running all jobs"""

from typing import List

import logging
from datetime import datetime
from random import random
from threading import Thread, Event, Lock

from job_runner import RegisteredJob

log = logging.getLogger(__name__)


class _JobThread(Thread):
    """Runs a single job on a single schedule"""

    def __init__(self, job: RegisteredJob):
        self.job = job
        self.stopping = Event()

        super().__init__()

    def run(self):
        log.info(
            "Thread for %s executing every %s + %s started",
            self.job.name,
            self.job.interval,
            self.job.variance,
        )

        # Use the variance as an initial delay to prevent thundering herd
        initial_delay = self.job.variance * random()
        
        if initial_delay:
            log.info("Waiting %s for first job run")

            # If we get interrupted during the initial wait,
            # we'll immediatly return and then exit at the
            # start of the while loop below
            self.stopping.wait(initial_delay.total_seconds())

        while not self.stopping.is_set():
            log.info("Starting %s", self.job.name)
            started_at = datetime.now()

            try:
                run_again = self.job.func()
                log.info("Finished %s successfully", self.job.name)

                if run_again:
                    log.info(
                        "%s indicated more work and is being immediatly scheduled",
                        self.job.name,
                    )
                    continue

            except Exception as exc:
                log.exception("Finished %s with exception: %s", self.job.name, exc)

            this_interval = self.job.interval + random() * self.job.variance
            next_run = started_at + this_interval
            now = datetime.now()
            delay = next_run - now

            if delay.total_seconds() > 0:
                log.info("%s not ready to be run, waiting %s", self.job.name, delay)

                # We do the delay inside of the event wait so that we can respond
                # immediatly to a stop signal. If we get a stop signal, we'll
                # stop the wait here and then immediatly exit the while loop
                self.stopping.wait(delay.total_seconds())
            else:
                log.info("%s being run with no delay", self.job.name)

        log.info("Thread running %s stopped", self.job.name)

    def request_stop(self):
        self.stopping.set()


class Coordinator(Thread):
    def __init__(self):
        self._evt = Event()
        self._workers: List[_JobThread] = []
        self._lock = Lock()

        super().__init__()

    def run(self):
        log.info("Job tracker thread started")
        self._evt.wait()
        log.info("Job tracker thread beginning shutdown")

        for worker in self._workers:
            log.debug("Signaling stop for %s", worker.job.name)
            worker.request_stop()

        for worker in self._workers:
            log.info("Waiting for %s shutdown", worker.job.name)
            worker.join()
            log.info("%s shutdown finished", worker.job.name)

        log.info("Job tracker thread finished")
        self._evt.clear()

    def add(self, job: RegisteredJob):
        """Add a job to the list of running jobs"""

        with self._lock:
            thread = _JobThread(job)
            self._workers.append(thread)
            thread.start()

    def request_stop(self):
        log.info("Signaling coordinator stop")
        self._evt.set()
