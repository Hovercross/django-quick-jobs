"""Command line interface to the job runner"""

from datetime import timedelta
import os
import sys
from threading import Event
from random import random
import signal
from threading import Thread
from typing import Iterable, List, Set

from django.core.management.base import BaseCommand, CommandParser, CommandError

from structlog import get_logger

from job_runner.runner import JobThread
from job_runner.registration import (
    RegisteredJob,
    import_default_jobs,
    import_jobs_from_module,
    import_jobs_from_modules,
)

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

        parser.add_argument(
            "--trial-run",
            action="store_const",
            const=True,
            default=False,
            help=(
                "Only compute the job list and immediately exit. "
                "Do begin job execution"
            ),
        )

        return super().add_arguments(parser)

    def handle(
        self,
        stop_after: int = 0,
        stop_variance: int = 0,
        stop_timeout: int = 5,
        include_jobs: List[str] = [],
        exclude_jobs: List[str] = [],
        trial_run: bool = False,
        *args,
        **kwargs,
    ):
        log = logger.bind()

        if include_jobs:
            jobs = get_jobs_for_included_names(set(include_jobs))
        elif exclude_jobs:
            jobs = get_jobs_for_excluded_names(set(exclude_jobs))
        else:
            jobs = import_default_jobs()

        job_names = {job.name for job in jobs}

        log.info(
            "Job list has been computed",
            to_run=sorted(job_names),
        )

        # Confirm all included jobs are there. If not, error
        for job_name in include_jobs:
            if job_name not in job_names:
                log.error("Included job does not exist", job_name=job_name)
                raise CommandError(f"Job '{job_name}' does not exist")

        if not jobs:
            log.error("There are no jobs to run, exiting")
            raise CommandError("There are no jobs to run")

        if trial_run:
            return

        request_stop = Event()
        # Signals can throw extra stuff into args and kwargs that we don't care about.
        # Wrap their handlers up to just call the coordinator stop
        def stop_signal_handler(*args, **kwargs):
            request_stop.set()

        got_fatal = _Flag()

        def on_fatal():
            log.error("A job runner failed fatally")
            got_fatal.set()
            request_stop.set()

        signal.signal(signal.SIGINT, stop_signal_handler)
        signal.signal(signal.SIGTERM, stop_signal_handler)

        threads = []

        for job in jobs:
            runner = JobThread(job, request_stop, on_fatal)
            runner.setDaemon(True)
            threads.append(runner)
            runner.start()

        if stop_after:
            final_delay = stop_after + stop_variance * random()
            log.info("Job runner stop registered", run_time=final_delay)

            _EventSetter(timedelta(seconds=final_delay), request_stop).start()

        log.info("All jobs have been started")
        request_stop.wait()
        log.info("Beginning job runner shutdown")

        waiter = _ThreadWaiter(threads)
        waiter.start()

        log.info("Waiting for all job stop", timeout=stop_timeout)
        waiter.join(stop_timeout)

        if waiter.is_alive():
            log.error("Job threads did not shut down, forcing exit")
            sys.exit(1)

        if got_fatal.is_set:
            sys.exit(1)


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
        self.setDaemon(True)

    def run(self):
        for t in self.threads:
            t.join()


class _Flag:
    def __init__(self):
        self._set = False

    def set(self):
        self._set = True

    @property
    def is_set(self):
        return self._set


class InvalidJobName(ValueError):
    def __init__(self, job_name: str):
        self.job_name = job_name

        super().__init__()


def _get_module_name(name: str):
    parts = name.split(".")
    if len(parts) < 2:
        raise InvalidJobName(name)

    return ".".join(parts[0:-1])


def get_module_names_for_included_jobs(names: Set[str]) -> Set[str]:
    out: Set[str] = set()

    return {_get_module_name(name) for name in names}


def get_jobs_for_included_names(names: Set[str]) -> Set[RegisteredJob]:
    module_names = get_module_names_for_included_jobs(names)
    jobs = import_jobs_from_modules(module_names)

    return {job for job in jobs if job.name in names}


def get_jobs_for_excluded_names(names: Set[str]) -> Set[RegisteredJob]:
    default_jobs = import_default_jobs()

    return {job for job in default_jobs if job.name not in names}
