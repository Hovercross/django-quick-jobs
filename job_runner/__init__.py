"""Job tracking library"""

from typing import List
import logging
import importlib

from django.conf import settings

from .tracker import JobTracker, RegisteredJob

log = logging.getLogger(__name__)


class _GlobalTracker:
    def __init__(self):
        self.did_imports = False
        self.tracker = JobTracker()

    def find_jobs(self) -> List[RegisteredJob]:
        """Get all the jobs from the tracker after finding all jobs"""

        self.import_once()
        return self.tracker.get_jobs()

    def import_once(self):
        """Run the imports exactly once"""
        if not self.did_imports:
            _run_imports()
            self.did_imports = True


def _run_imports():
    """Run all the job imports to trigger the global tracker"""
    
    for app_name in settings.INSTALLED_APPS:
        try:
            module_name = f"{app_name}.jobs"
            log.debug("Importing %s", module_name)

            # This will cause the decorators to be run and jobs to be registered
            importlib.import_module(module_name)
            log.info("Successfully imported %s", module_name)
        except ImportError:
            log.debug("Package %s did not have a jobs file", app_name)


_global_tracker = _GlobalTracker()

# Grab the default scheduler so libraries can just run @jobs.schedule(30)
schedule = _global_tracker.tracker.schedule
find_jobs = _global_tracker.find_jobs
