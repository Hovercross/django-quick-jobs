"""Command line interface to the job runner"""

from datetime import timedelta
import os
import sys
from threading import Event
from random import random
import signal
from threading import Thread
from typing import Callable, Iterable, List, Optional

from django.core.management.base import BaseCommand, CommandParser

from structlog import get_logger

from job_runner.singlton import discover_jobs
from job_runner.runner import JobThread

logger = get_logger(__name__)


class Command(BaseCommand):
    help = "Run all background jobs"

    def add_arguments(self, parser: CommandParser) -> None:
        group = parser.add_mutually_exclusive_group()

        group.add_argument(
            "--include-job",
            nargs="+",
            dest="include_jobs",
            metavar="JOB_NAME",
            default=[],
            help=(
                "A job name to include. If no jobs are included, "
                "all jobs except those excluded will be included"
            ),
        )

        group.add_argument(
            "--exclude-job",
            nargs="+",
            dest="exclude_jobs",
            metavar="JOB_NAME",
            default=[],
            help="A job name to exclude when all jobs are being included",
        )

        parser.add_argument(
            "--stop-after",
            type=int,
            default=0,
            metavar="SECONDS",
            help=(
                "Only run the job runner for a certian amount of time in seconds. "
                "This is useful if you want it to be restarted periodically, "
                "such as if things occasionally go wrong and a restart will fix them. "
                "For this to work, the process manager must restart the command after exit"
            ),
        )

        parser.add_argument(
            "--stop-variance",
            type=int,
            default=0,
            metavar="SECONDS",
            help=(
                "If using the stop after, an additional amount of random "
                "time to delay the stop for. Useful if you have multiple "
                "job runners and don't want a thundering herd"
            ),
        )

        parser.add_argument(
            "--stop-timeout",
            type=int,
            default=5,
            metavar="SECONDS",
            help=("When shutting down, how long to wait until a forced exit"),
        )

        return super().add_arguments(parser)

    def handle(
        self,
        stop_after: int = 0,
        stop_variance: int = 0,
        stop_timeout: int = 5,
        include_jobs: List[str] = [],
        exclude_jobs: List[str] = [],
        *args,
        **kwargs
    ):
        log = logger.bind()

        full_job_list = discover_jobs()
        to_execute = full_job_list[:]

        if include_jobs:
            to_execute = [job for job in to_execute if job.name in include_jobs]

        to_execute = [job for job in to_execute if job.name not in exclude_jobs]

        log.info(
            "Job list has been computed",
            to_run=sorted([job.name for job in to_execute]),
            to_skip=sorted(
                [job.name for job in full_job_list if job not in to_execute]
            ),
        )

        if not to_execute:
            log.error("There are no jobs to run, exiting")
            sys.exit(1)

        request_stop = Event()
        # Signals can throw extra stuff into args and kwargs that we don't care about.
        # Wrap their handlers up to just call the coordinator stop
        def stop_signal_handler(*args, **kwargs):
            request_stop.set()

        signal.signal(signal.SIGINT, stop_signal_handler)
        signal.signal(signal.SIGTERM, stop_signal_handler)

        threads = []

        for job in to_execute:
            runner = JobThread(job, request_stop)
            threads.append(runner)
            runner.start()

        # The coordinator has started successfully
        if stop_after:
            min_runtime = timedelta(seconds=stop_after)

            final_delay = stop_after + random() * stop_variance
            log.info("Job runner stop registered", run_time=final_delay)

            _EventSetter(timedelta(seconds=final_delay), request_stop).start()

            for job in to_execute:
                if job.variance > min_runtime:
                    log.warning(
                        "Job runner may be stopped before job executes",
                        job_name=job.name,
                        maximum_interval=job.variance.total_seconds(),
                        min_runtime=min_runtime.total_seconds(),
                    )

        log.info("All jobs have been started")
        request_stop.wait()
        log.info("Beginning job runner shutdown")

        waiter = _ThreadWaiter(threads)
        waiter.start()

        log.info("Waiting for all job stop", timeout=stop_timeout)
        waiter.join(stop_timeout)

        if waiter.is_alive():
            log.error("Job threads did not shut down, forcing exit")
            os._exit(1)


class _EventSetter(Thread):
    """Set an event after some amount of time"""

    def __init__(self, delay: timedelta, evt: Event):
        self.delay = delay
        self.evt = evt
        super().__init__()

    def run(self):
        self.evt.wait(self.delay.total_seconds())
        self.evt.set()


class _ThreadWaiter(Thread):
    """Wait for a number of additional threads"""

    def __init__(self, threads: Iterable[Thread]):
        self.threads = threads

        super().__init__()

    def run(self):
        for t in self.threads:
            t.join()
