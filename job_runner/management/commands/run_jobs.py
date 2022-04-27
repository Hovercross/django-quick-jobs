"""Command line interface to the job runner"""

import signal

from django.core.management.base import BaseCommand

from job_runner.singlton import import_jobs
from job_runner.coordinator import Coordinator


class Command(BaseCommand):
    help = "Run all background jobs"

    def handle(self, *args, **options):
        coordinator = Coordinator()
        coordinator.start()

        # Signals can throw extra stuff into args and kwargs that we don't care about.
        # Wrap their handlers up to just call the coordinator stop
        def stop_signal_handler(*args, **kwargs):
            coordinator.request_stop()

        signal.signal(signal.SIGINT, stop_signal_handler)
        signal.signal(signal.SIGTERM, stop_signal_handler)

        try:
            for job in import_jobs():
                coordinator.add(job)
        except Exception as exc:
            coordinator.request_stop()
            raise exc

        coordinator.join()
