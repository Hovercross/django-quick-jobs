"""Singleton tracker with automatic imports"""

from typing import List
import logging
import importlib
from datetime import timedelta

from django.conf import settings

from .tracker import Job, JobTracker, RegisteredJob, AutoTime

log = logging.getLogger(__name__)

_tracker = JobTracker()

def import_jobs() -> List[RegisteredJob]:
    """Import all jobs into the global tracker"""

    for app_name in settings.INSTALLED_APPS:
        try:
            module_name = f"{app_name}.jobs"
            log.debug("Importing %s", module_name)

            # This will cause the decorators to be run and jobs to be registered
            importlib.import_module(module_name)
            log.info("Successfully imported %s", module_name)
        except ImportError:
            log.debug("Package %s did not have a jobs file", app_name)
    
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

    _tracker.tracker.schedule_job(func, interval, variance)
