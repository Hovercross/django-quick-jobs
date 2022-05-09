"""Tracking utils for job runner"""

import importlib
import inspect
from threading import Event

from typing import Callable, Iterable, Optional, Set
from datetime import timedelta

from structlog import get_logger

from django.conf import settings

from .environment import RunEnv, get_environments
from .time import AutoTime, auto_time, auto_time_default

Job = Callable[[RunEnv], None]

logger = get_logger(__name__)


class RegisteredJob:
    """A job that has been registered to be run periodically"""

    def __init__(
        self,
        interval: timedelta,
        variance: timedelta,
        timeout: Optional[timedelta],
        func: Job,
    ):
        self._interval = interval
        self._variance = variance
        self._func = func
        self._timeout = timeout

    @property
    def name(self):
        """The full name of the function to be called"""
        return f"{self._func.__module__}.{self._func.__name__}"

    @property
    def timeout(self) -> Optional[timedelta]:
        return self._timeout

    @property
    def interval(self) -> timedelta:
        return self._interval

    @property
    def variance(self) -> timedelta:
        return self._variance

    def check_callable_valid(self):
        # We don't need a "real" stop event since we aren't callint the function
        sample_env, _ = get_environments(Event())
        signature = inspect.signature(self._func)
        # This will throw a type error if it isn't callable
        signature.bind(sample_env)

    def __call__(self, env: RunEnv):
        return self._func(env)


def register_job(
    interval: AutoTime,
    variance: Optional[AutoTime] = None,
    timeout: Optional[AutoTime] = None,
):
    """Decorator to schedule the job to be run every
    interval plus a random time up to variance"""

    def decorator(func: Job):
        return RegisteredJob(
            interval=auto_time(interval),
            variance=auto_time_default(variance, timedelta(0)),
            timeout=auto_time_default(timeout, None),
            func=func,
        )

    return decorator


def import_jobs_from_module(module_name: str) -> Iterable[RegisteredJob]:
    """Get all the registered jobs from a given module"""

    log = logger.bind(module_name=module_name)

    log.debug("Importing module")
    module = importlib.import_module(module_name)

    for item in module.__dict__.values():
        if isinstance(item, RegisteredJob):
            yield item


def import_default_jobs() -> Set[RegisteredJob]:
    """Get all the registered jobs from all Django installed apps"""

    out: Set[RegisteredJob] = set()

    for app_name in settings.INSTALLED_APPS:
        log = logger.bind(app_name=app_name)

        if app_name.startswith("django."):
            log.debug("Skipping default import")
            continue

        module_name = f"{app_name}.jobs"
        log = log.bind(module_name=module_name)

        try:
            log.debug("Importing module")
            for job in import_jobs_from_module(module_name):
                out.add(job)

            log.info("Module successfully imported")

        except ImportError:
            log.debug("Module not imported")

    return out
