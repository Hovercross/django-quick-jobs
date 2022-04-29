"""Command line interface to the job runner"""

from datetime import timedelta
import os
import sys
from threading import Event
from random import random
import signal
from threading import Thread
from typing import Callable, List, Optional

from django.core.management.base import BaseCommand, CommandParser

from structlog import get_logger

from job_runner.singlton import import_jobs
from job_runner.coordinator import Coordinator

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
        **options
    ):
        log = logger.bind()

        full_job_list = import_jobs()
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

        coordinator = Coordinator()
        coordinator.start()

        try:
            for job in to_execute:
                log.info("Adding job", job_name=job.name)
                coordinator.add(job)

        except Exception as exc:
            log.exception("Got exception when adding jobs", error=str(exc))
            coordinator.request_stop()
            coordinator.join(stop_timeout)

            if coordinator.is_alive():
                log.error("Coordinator stop timeout exceeded, forcing exit")
                os._exit(1)

            sys.exit(1)

        # The coordinator has started successfully
        if stop_after:
            min_runtime = timedelta(seconds=stop_after)
            max_runtime = timedelta(seconds=(stop_after + stop_variance))

            final_delay = stop_after + random() * stop_variance
            log.info("Adding stop watcher after %d seconds", final_delay)

            CancelableDelay(
                final_delay, request_stop.set, request_stop, name="Job stop delay"
            ).start()

            for job in to_execute:
                if job.minimum_interval > max_runtime:
                    log.error(
                        "Job runner will be stopped before job can execute",
                        job_name=job.name,
                        minimum_interval=job.minimum_interval.total_seconds(),
                        max_runtime=max_runtime.total_seconds(),
                    )
                elif job.maximum_interval > min_runtime:
                    log.warning(
                        "Job runner may be stopped before job can execute",
                        job_name=job.name,
                        maximum_interval=job.maximum_interval.total_seconds(),
                        min_runtime=min_runtime.total_seconds(),
                    )

        log.info("Job runner has finished startup")
        request_stop.wait()
        log.info("Beginning job runner shutdown")

        coordinator.request_stop()

        coordinator.join(stop_timeout)
        if coordinator.is_alive():
            log.error("Coordinator did not shut down, forcing exit")
            os._exit(1)


class CancelableDelay(Thread):
    """A thread that will run a callback after a
    certain amount of time unless it is canceled"""

    def __init__(
        self,
        delay: float,
        cb: Callable[[], None],
        cancel: Event,
        name: Optional[str] = None,
    ):
        super().__init__()
        self._delay = delay
        self._cb = cb
        self._cancel = cancel
        self._log = logger.bind()
        if name:
            self._log = self._log.bind(name=name)

    def run(self):
        self._log.debug("Beginning execution")
        self._cancel.wait(self._delay)
        if self._cancel.is_set():
            self._log.debug("Execution canceled")
            return

        self._log.info("Timeout threshold met")
        self._cb()
