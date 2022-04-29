"""Command line interface to the job runner"""

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
            "--job-name",
            nargs="+",
            help="A job name to run. If not job names are provided, all jobs will be run",
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
        job_name: List[str] = [],
        *args,
        **options
    ):
        log = logger.bind()

        coordinator = Coordinator()
        coordinator.start()

        # Signals can throw extra stuff into args and kwargs that we don't care about.
        # Wrap their handlers up to just call the coordinator stop
        def stop_signal_handler(*args, **kwargs):
            coordinator.request_stop()

        signal.signal(signal.SIGINT, stop_signal_handler)
        signal.signal(signal.SIGTERM, stop_signal_handler)

        try:
            got_job = False
            for job in import_jobs():
                if not job_name or job.name in job_name:
                    log.info("Adding job", job_name=job.name)
                    coordinator.add(job)
                    got_job = True
                else:
                    log.debug("Skipping job", job_name=job.name)

        except Exception as exc:
            coordinator.request_stop()
            raise exc

        if not got_job:
            log.error("Coordinator is not running any jobs, exiting")
            coordinator.request_stop()
            coordinator.join()
            sys.exit(1)

        done_evt = Event()
        if stop_after:
            variance = random() * stop_after_variance
            final_delay = stop_after + variance
            log.info("Adding restart watcher after %d seconds", final_delay)

            t = StopThread(final_delay, coordinator.request_stop, done_evt)
            t.start()

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
