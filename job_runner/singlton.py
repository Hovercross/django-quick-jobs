"""Singleton tracker with automatic imports"""

from audioop import add
from typing import List, Set
import importlib
from datetime import timedelta

from structlog import get_logger

from django.conf import settings

from .tracker import Job, JobTracker, RegisteredJob, AutoTime

logger = get_logger(__name__)

_tracker = JobTracker()


def auto_import_jobs(additional_module_names: Set[str] = set()) -> List[RegisteredJob]:
    """Import all jobs into the global tracker"""

    module_names = {
        f"{app_name}.jobs"
        for app_name in settings.INSTALLED_APPS
        if not app_name.startswith("django.")
    }

    module_names |= additional_module_names

    for module_name in module_names:
        log = logger.bind(module_name=module_name)

        try:
            log.debug("Importing module")

            # This will cause the decorators to be run and jobs to be registered
            importlib.import_module(module_name)
            log.info("Module successfully imported")

        except ImportError:
            log.debug("Module not imported")

    return _tracker.get_jobs()


def schedule_job(func: Job, interval: AutoTime = None, variance: AutoTime = None):
    """Schedule a given job into the global tracker"""

    _tracker.schedule_job(func, interval, variance)


def schedule(interval: AutoTime = None, variance: AutoTime = None):
    """Decorator to schedule the job to be run every
    interval plus a random time up to variance"""

    def decorator(func: Job):
        schedule_job(func, interval, variance)

        return func

    return decorator
