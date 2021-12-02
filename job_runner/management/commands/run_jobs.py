"""Command line interface to the job runner"""

import signal

from django.core.management.base import BaseCommand

from job_runner import find_jobs
from job_runner.coordinator import Coordinator

class Command(BaseCommand):
    help = 'Run all background jobs'

    def handle(self, *args, **options):
        coordinator = Coordinator()
        coordinator.start()

        def stop_signal(*args, **kwargs):
            coordinator.request_stop()

        signal.signal(signal.SIGINT, stop_signal)
        signal.signal(signal.SIGTERM, stop_signal)

        for job in find_jobs():
            coordinator.add(job)

        coordinator.join()
