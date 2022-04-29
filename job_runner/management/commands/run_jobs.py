"""Command line interface to the job runner"""

from datetime import timedelta
import sys
from threading import Event
from random import random
import signal
from threading import Thread
from typing import Callable, List

from django.core.management.base import BaseCommand, CommandParser

from structlog import get_logger

from job_runner.singlton import import_jobs
from job_runner.coordinator import Coordinator

logger = get_logger()


class Command(BaseCommand):
    help = "Run all background jobs"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--include-job",
            nargs="+",
            dest="include_jobs",
            default=[],
            help=(
                "A job name to include. If no jobs are included, "
                "all jobs except those excluded will be included"
            ),
        )

        parser.add_argument(
            "--exclude-job",
            nargs="+",
            dest="exclude_jobs",
            default=[],
            help="A job name to exclude, which takes prescience over included jobs",
        )

        parser.add_argument(
            "--stop-after",
            type=int,
            default=0,
            help=(
                "Only run the job runner for a certian amount of time in seconds. "
                "This is useful if you want it to be restarted periodically, "
                "such as if things occasionally go wrong and a restart will fix them"
            ),
        )

        parser.add_argument(
            "--stop-after-variance",
            type=int,
            default=0,
            help=(
                "If using the stop after, an additional amount of random "
                "time to delay the stop for. Useful if you have multiple "
                "job runners and don't want a thundering herd"
            ),
        )

        return super().add_arguments(parser)

    def handle(
        self,
        stop_after: int = 0,
        stop_after_variance: int = 0,
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

        coordinator = Coordinator()
        coordinator.start()

        # Signals can throw extra stuff into args and kwargs that we don't care about.
        # Wrap their handlers up to just call the coordinator stop
        def stop_signal_handler(*args, **kwargs):
            coordinator.request_stop()

        signal.signal(signal.SIGINT, stop_signal_handler)
        signal.signal(signal.SIGTERM, stop_signal_handler)

        try:
            for job in to_execute:
                log.info("Adding job", job_name=job.name)
                coordinator.add(job)

        except Exception as exc:
            log.exception("Got exception when adding jobs", error=str(exc))
            coordinator.request_stop()
            coordinator.join()
            sys.exit(1)

        # The coordinator has started successfully
        done_evt = Event()
        if stop_after:
            min_runtime = timedelta(seconds=stop_after)
            max_runtime = timedelta(seconds=(stop_after + stop_after_variance))

            final_delay = stop_after + random() * stop_after_variance
            log.info("Adding restart watcher after %d seconds", final_delay)

            t = StopThread(final_delay, coordinator.request_stop, done_evt)
            t.start()

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

        coordinator.join()
        done_evt.set()


class StopThread(Thread):
    """Stop the coordinator after some amount of time"""

    def __init__(self, delay: float, cb: Callable[[], None], cancel: Event):
        super().__init__()
        self.delay = delay
        self.cb = cb
        self.cancel = cancel
        self.log = logger.bind(process="stop thread")

    def run(self):
        self.log.debug("Beginning stop wait")
        self.cancel.wait(self.delay)
        if self.cancel.is_set():
            self.log.debug("Closing thread due to cancelation")
            return

        self.log.info("Stop timer triggered, executing stop request")
        self.cb()
        self.log.debug("Stop timer exiting")
