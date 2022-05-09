"""Command line interface to the job runner"""

from datetime import timedelta
import time
import sys
from threading import Event, Thread
from random import random
import signal
from typing import Iterable, List, Set

from django.core.management.base import BaseCommand, CommandParser

from structlog import get_logger

from job_runner.runner import JobThread
from job_runner.registration import (
    RegisteredJob,
    import_default_jobs,
    import_jobs_from_module,
)

from job_runner.timeouts import TimeoutTracker

logger = get_logger(__name__)


class Command(BaseCommand):
    help = "Run all background jobs"

    def add_arguments(self, parser: CommandParser) -> None:
        group = parser.add_mutually_exclusive_group()

        group.add_argument(
            "--include-job",
            dest="include_jobs",
            metavar="JOB_NAME",
            default=[],
            action="append",
            help=(
                "A job name to include. If no jobs are included, "
                "all jobs except those excluded will be included"
            ),
        )

        group.add_argument(
            "--exclude-job",
            dest="exclude_jobs",
            metavar="JOB_NAME",
            default=[],
            action="append",
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
            log.debug("Using job inclusion handler", include_jobs=include_jobs)
            try:
                jobs = get_jobs_for_included_names(set(include_jobs))
            except InvalidJobName as exc:
                log.error("Included job name was invalid", job_name=exc.job_name)
                sys.exit(1)
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
                sys.exit(1)

        if not jobs:
            log.error("There are no jobs to run")
            sys.exit(1)

        jobs_ok = True
        for job in jobs:
            try:
                job.check_callable_valid()
            except TypeError as exc:
                jobs_ok = False
                log.error(
                    "Job is not callable. "
                    "Make sure the job takes one parameter of "
                    "job_tracker.environment.RunEnv",
                    job_name=job.name,
                    error=str(exc),
                )

        if not jobs_ok:
            sys.exit(1)

        if trial_run:
            return

        request_stop = Event()
        # Signals can throw extra stuff into args and kwargs that we don't care about.
        # Wrap their handlers up to just call the coordinator stop
        def stop_signal_handler(*args, **kwargs):
            request_stop.set()

        timeout_tracker = TimeoutTracker(request_stop)
        timeout_tracker.start()
        got_fatal = Event()

        def on_fatal():
            log.error("A job runner failed fatally")
            got_fatal.set()
            request_stop.set()

        signal.signal(signal.SIGINT, stop_signal_handler)
        signal.signal(signal.SIGTERM, stop_signal_handler)
        signal.signal(signal.SIGQUIT, stop_signal_handler)

        threads: List[JobThread] = []

        for job in jobs:
            runner = JobThread(job, request_stop, on_fatal, timeout_tracker)
            runner.daemon = True
            threads.append(runner)
            runner.start()

        if stop_after:
            final_delay = stop_after + stop_variance * random()
            log.info("Job runner stop registered", run_time=final_delay)

            def stop_callback():
                log.info("Setting stop event due to stop timeout")
                request_stop.set()

            timeout_tracker.add_timeout(timedelta(seconds=final_delay), stop_callback)

        log.info("All jobs have been started")
        request_stop.wait()
        log.info("Beginning job runner shutdown")

        shutdown_started_at = time.monotonic()
        log.info("Waiting for all jobs to stop", timeout=stop_timeout)

        for thread in threads:
            time_left = stop_timeout - (time.monotonic() - shutdown_started_at)

            thread.join(timeout=time_left)
            if thread.is_alive():
                log_alive_threads_and_exit(log, threads)

        log.info("All jobs have stopped")

        if got_fatal.is_set():
            log.warning("A fatal error was thrown from a job, exiting with code 1")
            sys.exit(1)


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

    jobs: Set[RegisteredJob] = set()

    for module_name in module_names:
        try:
            for job in import_jobs_from_module(module_name):
                jobs.add(job)
        except ModuleNotFoundError:
            logger.warning("Module not found during import", module_name=module_name)

    return {job for job in jobs if job.name in names}


def get_jobs_for_excluded_names(names: Set[str]) -> Set[RegisteredJob]:
    default_jobs = import_default_jobs()

    return {job for job in default_jobs if job.name not in names}


def log_alive_threads_and_exit(log, threads: Iterable[JobThread]):
    for thread in threads:
        if thread.is_alive():
            log.error("Job thread is still alive", job_name=thread.job.name)

    sys.exit(1)
