"""Tracking utils for job runner"""

from typing import Callable, List, Optional, Union
from datetime import timedelta
from dataclasses import dataclass
from threading import Lock

Job = Callable[[], Optional[bool]]

AutoTime = Union[None, timedelta, int, float]


@dataclass(frozen=True)
class RegisteredJob:
    """A job that has been registered to be run periodically"""
    interval: timedelta
    variance: timedelta
    func: Job

    @property
    def name(self):
        """The full name of the function to be called"""
        return f"{self.func.__module__}.{self.func.__name__}"


class JobTracker:
    """Track the registered jobs"""

    def __init__(self):
        self._lock = Lock()
        self._jobs: List[RegisteredJob] = []

    def add_job(self, job: RegisteredJob):
        """Add a tracked job"""
        with self._lock:
            self._jobs.append(job)

    def schedule(self, interval: AutoTime = None, variance: AutoTime = None):
        """Decorator to schedule the job to be run every interval
        plus a random time up to variance"""

        interval = _read_auto(interval, timedelta(seconds=0))
        variance = _read_auto(variance, timedelta(seconds=0))

        def decorator(func: Callable[[], None]):
            obj = RegisteredJob(interval=interval, variance=variance, func=func)

            self.add_job(obj)

            return func

        return decorator

    def get_jobs(self) -> List[RegisteredJob]:
        """Get all the jobs that have been registered"""
        return self._jobs[:]


def _read_auto(val: AutoTime, default: timedelta) -> timedelta:
    if val is None:
        return default

    if isinstance(val, timedelta):
        return val

    return timedelta(seconds=val)
