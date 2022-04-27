"""Singleton tracker with automatic imports"""

from typing import List
import importlib
from datetime import timedelta

from structlog import get_logger

from django.conf import settings

from .tracker import Job, JobTracker, RegisteredJob, AutoTime

logger = get_logger()

_tracker = JobTracker()


def import_jobs() -> List[RegisteredJob]:
    """Import all jobs into the global tracker"""

    for app_name in settings.INSTALLED_APPS:
        module_name = f"{app_name}.jobs"
        log = logger.bind(module_name=module_name, app_name=app_name)

        try:
            log.debug("Importing module")

            # This will cause the decorators to be run and jobs to be registered
            importlib.import_module(module_name)
            log.info("Module successfully imported")
        except ImportError:
            log.debug("Package did not have a jobs files")

    return _tracker.get_jobs()


def schedule(interval: AutoTime = None, variance: AutoTime = None):
    """Decorator to schedule the job to be run every
    interval plus a random time up to variance"""

    def decorator(func: Job):
        _tracker.schedule_job(func, interval, variance)

        return func

    return decorator


def schedule_job(func: Job, interval: AutoTime = None, variance: AutoTime = None):
    """Schedule a given job into the global tracker"""

    _tracker.schedule_job(func, interval, variance)
